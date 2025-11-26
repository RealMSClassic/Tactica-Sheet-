from __future__ import annotations
import flet as ft
import base64, os, time, re, asyncio, urllib.request
from datetime import datetime

DEBUG_IMAGES = True

# Carpeta local de cache opcional (si la usás)
IMAGES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../..', 'images_cache')
)

def _now_str() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def _dprint(*a, **k):
    
    if DEBUG_IMAGES:
        print(*a, **k, flush=True)

def _guess_mime(b: bytes) -> str:
    if not b or len(b) < 12:
        return "image/jpeg"
    if b.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if b.startswith(b"\x89PNG"):
        return "image/png"
    if b.startswith(b"GIF8"):
        return "image/gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"

def _to_b64(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def _make_data_url(b: bytes) -> str:
    return f"data:{_guess_mime(b)};base64,{_to_b64(b)}"

def _safe_update(ctrl: ft.Control):
    try:
        if getattr(ctrl, "page", None):
            ctrl.update()
    except Exception as ex:
        pass
        _dprint(f"[IMG] safe_update skip: {ex}")

_RX_FILE_D = re.compile(r"/file/d/([^/]+)")
_RX_Q_ID   = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")

def extract_drive_id(url_or_id: str) -> str:
    if not url_or_id: return ""
    m = _RX_FILE_D.search(url_or_id)
    if m: return m.group(1)
    m = _RX_Q_ID.search(url_or_id)
    if m: return m.group(1)
    return (url_or_id or "").strip()

def drive_download_url(fid: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={fid}"

def fetch_bytes_sync(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.read()
    except Exception as ex:
        _dprint(f"[fetch] ERROR url={url} ex={ex}")
        return None

def cargar_imagen_data_url_local(recid_imagen: str) -> tuple[str | None, list[str]]:
    tried = []
    if not recid_imagen: return None, tried
    for ext in (".jpg",".jpeg",".png",".webp"):
        p = os.path.join(IMAGES_DIR, f"{recid_imagen}{ext}")
        tried.append(p)
        if os.path.isfile(p):
            try:
                with open(p,"rb") as f: b = f.read()
                return _make_data_url(b), tried
            except Exception as ex:
                _dprint(f"[IMG/LOCAL] error leyendo {p}: {ex}")
                return None, tried
    return None, tried

def _set_img_src(img: ft.Image, src: str) -> str:
    img.src = src
    try:
        if getattr(img, "page", None):
            img.update()
            return "OK/UPDATED"
        return "OK/SET_ONLY"
    except Exception as ex:
        return f"DEFERRED({ex})"

def _set_busy(meta: dict, on: bool):
    """Muestra/oculta barra y habilita/deshabilita controles si están presentes."""
    if not isinstance(meta, dict):
        return
    busy = meta.get("busy")
    dis_list = meta.get("disable_on_busy") or []
    err_lbl = meta.get("error_label")

    if err_lbl:
        # limpiar error al iniciar
        if on:
            err_lbl.visible = False
            err_lbl.value = ""
            _safe_update(err_lbl)

    if busy:
        busy.visible = on
        _safe_update(busy)

    for c in dis_list:
        try:
            c.disabled = on
            _safe_update(c)
        except Exception:
            pass

async def ensure_image_for_container_async(container: ft.Container):
    """
    Espera que el container tenga en .data:
      - recid_imagen: str (data:, url http(s) o id local/código)
      - img_control:  ft.Image
      - busy:         ft.ProgressBar (opcional)
      - error_label:  ft.Text (opcional)
      - disable_on_busy: list[Control] (opcional)
    """
    meta = getattr(container, "data", None)
    cid = hex(id(container))
    if not isinstance(meta, dict):
        _dprint(f"[IMG] {cid} sin meta; skip"); 
        return

    recid_imagen: str = meta.get("recid_imagen") or ""
    img_control: ft.Image | None = meta.get("img_control")
    err_lbl: ft.Text | None = meta.get("error_label")

    t0 = time.perf_counter()
    _dprint(f"[IMG] START {_now_str()} cid={cid} recid_imagen={repr(recid_imagen)}")

    try:
        if not img_control:
            _set_busy(meta, False)
            dur = int((time.perf_counter()-t0)*1000)
            _dprint(f"[IMG] END   {_now_str()} cid={cid} -> SIN_CONTROL duration={dur}ms"); return
        if not recid_imagen:
            _set_busy(meta, False)
            dur = int((time.perf_counter()-t0)*1000)
            _dprint(f"[IMG] END   {_now_str()} cid={cid} -> SIN_DATO duration={dur}ms"); return

        # encender busy + bloquear
        _set_busy(meta, True)

        # 1) si ya viene data-url
        if recid_imagen.startswith("data:"):
            res = _set_img_src(img_control, recid_imagen)
            _set_busy(meta, False)
            dur = int((time.perf_counter()-t0)*1000)
            _dprint(f"[IMG] END   {_now_str()} cid={cid} -> OK(DATA-URL) {res} duration={dur}ms"); return

        # 2) si es http(s)
        if recid_imagen.startswith(("http://","https://")):
            url = recid_imagen
            if "drive.google.com" in url:
                fid = extract_drive_id(url)
                url = drive_download_url(fid)
            b = await asyncio.to_thread(fetch_bytes_sync, url)
            if b:
                data_url = _make_data_url(b)
                res = _set_img_src(img_control, data_url)
                _set_busy(meta, False)
                dur = int((time.perf_counter()-t0)*1000)
                _dprint(f"[IMG] END   {_now_str()} cid={cid} -> OK(URL->DATA-URL) {res} bytes={len(b)} duration={dur}ms"); return
            # Fallback: setear src directo (puede fallar en web por CSP)
            res = _set_img_src(img_control, recid_imagen)
            # mostrar error para dejar rastro
            if err_lbl:
                err_lbl.visible = True
                err_lbl.value = "No se pudo obtener la imagen (fallo descarga)."
                _safe_update(err_lbl)
            _set_busy(meta, False)
            dur = int((time.perf_counter()-t0)*1000)
            _dprint(f"[IMG] END   {_now_str()} cid={cid} -> FALLBACK(URL) {res} duration={dur}ms"); return

        # 3) intentar cache local por ID
        data_url, tried = cargar_imagen_data_url_local(recid_imagen)
        if data_url:
            res = _set_img_src(img_control, data_url)
            _set_busy(meta, False)
            dur = int((time.perf_counter()-t0)*1000)
            _dprint(f"[IMG] END   {_now_str()} cid={cid} -> OK(LOCAL) {res} duration={dur}ms"); return

        # Sin resultados
        if err_lbl:
            err_lbl.visible = True
            err_lbl.value = "Imagen no encontrada."
            _safe_update(err_lbl)

        _set_busy(meta, False)
        dur = int((time.perf_counter()-t0)*1000)
        _dprint(f"[IMG] END   {_now_str()} cid={cid} -> NO_ENCONTRADA duration={dur}ms IMAGES_DIR={IMAGES_DIR} tried={tried if recid_imagen else []}")

    except Exception as ex:
        if err_lbl:
            err_lbl.visible = True
            err_lbl.value = f"Error al cargar imagen: {ex}"
            _safe_update(err_lbl)
        _set_busy(meta, False)
        dur = int((time.perf_counter()-t0)*1000)
        _dprint(f"[IMG] END   {_now_str()} cid={cid} -> ERROR: {ex} duration={dur}ms")

# ---- Wrapper compat: agenda la tarea async si hay loop, o la corre si no.
def renderizar_imagen_asinc(container: ft.Container):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ensure_image_for_container_async(container))
    except RuntimeError:
        asyncio.run(ensure_image_for_container_async(container))
