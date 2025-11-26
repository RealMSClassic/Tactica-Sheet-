from __future__ import annotations
import os, re

# Carpeta local donde guardás/copias las imágenes renderizadas/cache
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../..', 'TacticaGestorSheet', 'ImagenGestor')
)

_RX_FILE_D = re.compile(r"/file/d/([^/]+)")
_RX_Q_ID   = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")

def extract_drive_id(url_or_id: str) -> str:
    if not url_or_id:
        return ""
    m = _RX_FILE_D.search(url_or_id)
    if m:
        return m.group(1)
    m = _RX_Q_ID.search(url_or_id)
    if m:
        return m.group(1)
    return (url_or_id or "").strip()

def delete_local_variants_by_id(image_id: str, base_dir: str = BASE_DIR) -> tuple[bool, list[str]]:
    """
    Elimina archivos {image_id}.{ext} para ext en [jpg, jpeg, png, webp] dentro de base_dir.
    Devuelve (hubo_alguna_borrada, rutas_intentadas).
    """
    tried, deleted_any = [], False
    if not image_id:
        return False, tried
    os.makedirs(base_dir, exist_ok=True)
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = os.path.join(base_dir, f"{image_id}.{ext}")
        tried.append(p)
        if os.path.isfile(p):
            try:
                os.remove(p)
                deleted_any = True
            except Exception:
                pass
    return deleted_any, tried

def delete_local_image_by_link(link: str, base_dir: str = BASE_DIR) -> tuple[bool, list[str], str]:
    """
    Extrae el ID del link (Drive u otros con ?id=) y borra las variantes en base_dir.
    Devuelve (ok, rutas_intentadas, image_id_extraido)
    """
    image_id = extract_drive_id(link or "")
    ok, tried = delete_local_variants_by_id(image_id, base_dir) if image_id else (False, [])
    return ok, tried, image_id
