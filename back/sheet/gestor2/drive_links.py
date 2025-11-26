# back/utils/drive_links.py
from urllib.parse import urlparse, parse_qs

def extract_drive_id_from_url(s: str) -> str:
    s = (s or "").strip()
    if not s: return ""
    if "id=" in s:
        qs = parse_qs(urlparse(s).query)
        return (qs.get("id", [""])[0] or "").strip()
    if "/d/" in s:
        try:
            return s.split("/d/", 1)[1].split("/", 1)[0]
        except Exception:
            return ""
    return s

def drive_embed_src(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if not s: return ""
    file_id = extract_drive_id_from_url(s) if s.startswith(("http://","https://")) else s
    return f"https://drive.google.com/uc?export=view&id={file_id}" if file_id else ""

def product_image_src(prod: dict, backend) -> str:
    recid = (prod.get("ID_Imagen") or "").strip()
    if not recid: return ""
    imagen_map = getattr(backend, "imagen_by_recid", {}) or {}
    row = imagen_map.get(recid) or {}
    raw = row.get("ID_imagen") or row.get("id_imagen") or row.get("ID_nombre") or ""
    return drive_embed_src(raw)
