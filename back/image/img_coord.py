# ./back/image/img_coord.py
from __future__ import annotations
import asyncio, base64, re, urllib.request
from typing import Tuple, Optional

# PNG 1x1 transparente
PLACEHOLDER_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)

# ---------- URL helpers (Drive y genéricas) ----------
_DRIVE_ID_RE = re.compile(r"/d/([^/]+)/")

def extract_drive_id(url_or_id: str) -> str:
    if not url_or_id:
        return ""
    m = _DRIVE_ID_RE.search(url_or_id)
    return m.group(1) if m else url_or_id.strip()

def normalize_image_url(id_or_url: str) -> str:
    """
    Si parece un link de Drive, devuelve 'uc?export=download&id=...'
    Caso contrario, devuelve tal cual (URL directa de imagen).
    """
    s = (id_or_url or "").strip()
    if not s:
        return ""
    if "drive.google.com" in s or _DRIVE_ID_RE.search(s):
        fid = extract_drive_id(s)
        return f"https://drive.google.com/uc?export=download&id={fid}"
    return s

# ---------- Fetch + tipo ----------
def fetch_bytes_and_type_sync(url: str) -> Tuple[Optional[bytes], str]:
    if not url:
        return None, ""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            b = resp.read()
            ct = resp.headers.get("Content-Type", "")
        return b, ct
    except Exception as ex:
        print(f"[imgcoord.fetch] ERROR url={url} ex={ex}", flush=True)
        return None, ""

def looks_like_html(b: Optional[bytes]) -> bool:
    if not b:
        return False
    head = b[:256].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<html" in head

def is_image_content_type(ct: str) -> bool:
    return (ct or "").lower().startswith("image/")

# ---------- base64 ----------
def to_b64(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

# ---------- Coordinador con cache + single-flight ----------
class ImageCoordinator:
    """
    - cache: RecID_imagen -> base64 (o None si falló)
    - inflight: RecID_imagen -> asyncio.Future compartido (single-flight)
    - sem: limita concurrencia de descargas
    """
    def __init__(self, max_concurrency: int = 6):
        self.cache: dict[str, Optional[str]] = {}
        self.inflight: dict[str, asyncio.Future] = {}
        self.sem = asyncio.Semaphore(max_concurrency)

    async def ensure_b64(self, recid_imagen: str, id_nombre: Optional[str]) -> Optional[str]:
        """
        Devuelve base64 para ese RecID_imagen (usa id_nombre como URL o ID de Drive).
        Deduplica llamadas y limita concurrencia.
        """
        rid = (recid_imagen or "").strip()
        if not rid:
            return None

        # cache hit
        if rid in self.cache:
            return self.cache[rid]

        # single-flight: si ya hay un fut en curso, esperamos
        if rid in self.inflight:
            return await self.inflight[rid]

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self.inflight[rid] = fut

        async def worker():
            b64: Optional[str] = None
            try:
                url = normalize_image_url(id_nombre or "")
                if url:
                    async with self.sem:
                        b, ct = await asyncio.to_thread(fetch_bytes_and_type_sync, url)
                    if b and (is_image_content_type(ct) or not looks_like_html(b)):
                        b64 = await asyncio.to_thread(to_b64, b)
                    else:
                        print(f"[imgcoord.worker] not-image or html rid={rid} ct={ct!r}", flush=True)
                else:
                    print(f"[imgcoord.worker] empty url/id for rid={rid}", flush=True)
            except Exception as ex:
                print(f"[imgcoord.worker] ERROR rid={rid} ex={ex}", flush=True)
            finally:
                self.cache[rid] = b64
                fut.set_result(b64)
                self.inflight.pop(rid, None)

        asyncio.create_task(worker())
        return await fut

# ---------- instancia global ----------
_global_coord: ImageCoordinator | None = None

def get_img_coordinator() -> ImageCoordinator:
    global _global_coord
    if _global_coord is None:
        _global_coord = ImageCoordinator(max_concurrency=6)
    return _global_coord
