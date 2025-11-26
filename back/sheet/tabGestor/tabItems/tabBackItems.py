# ./back/sheet/tabGestor/tabItems/tabBackItems.py
from __future__ import annotations
from typing import List, Dict, Optional
from uuid import uuid4
import os

try:
    from back.sheet.producto_api import ProductoAPI  # API equivalente a DepositoAPI
except Exception:
    ProductoAPI = None

try:
    from back.sheet.imagen_api import ImagenAPI
except Exception:
    ImagenAPI = None

class ItemsBackend:
    """
    Backend para Items (productos).
    - refresh_all / refresh_items / refresh_imagenes
    - filter(q)
    - add / update / delete
    - remove_image_for_item(recid)
    - upload_and_attach_image(...)

    Mapas:
    - item_by_recid: RecID(producto) -> dict
    - img_by_recid : RecID(imagen)   -> ID_nombre(link)
    """

    def __init__(self, page=None, bus: Optional[object] = None):
        self.page = page
        self.bus = bus

        self.sheet_id = None
        if page is not None:
            self.sheet_id = (
                page.client_storage.get("active_sheet_id")
                or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
            )

        self.api = ProductoAPI(page, self.sheet_id) if (ProductoAPI and page is not None) else None
        self.api_img = ImagenAPI(page, self.sheet_id) if (ImagenAPI and page is not None) else None

        self.items: List[Dict] = []
        self.item_by_recid: Dict[str, Dict] = {}

        self.imagenes: List[Dict] = []
        self.img_by_recid: Dict[str, str] = {}

    # ---- attach page opcional ----
    def attach_page(self, page):
        self.page = page
        self.sheet_id = (
            page.client_storage.get("active_sheet_id")
            or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
        )
        self.api = ProductoAPI(page, self.sheet_id) if ProductoAPI else None
        self.api_img = ImagenAPI(page, self.sheet_id) if ImagenAPI else None

    # ---- Refresh ----
    def refresh_imagenes(self):
        if not self.api_img:
            self.imagenes = []
            self.img_by_recid = {}
            return
        self.imagenes = self.api_img.list()
        self.img_by_recid = {(i.get("RecID") or ""): (i.get("ID_nombre") or "") for i in self.imagenes}

    def refresh_items(self):
        self.refresh_imagenes()
        if not self.api:
            self.items = []
            self.item_by_recid = {}
            return
        self.items = self.api.list()
        for r in self.items:
            rid = (r.get("RecID_imagen") or r.get("ID_Imagen") or "").strip()
            link = self.img_by_recid.get(rid, "").strip()
            if link:
                r["imagen_url"] = link
        self.item_by_recid = {r.get("RecID", ""): r for r in self.items}

    def refresh_all(self):
        self.refresh_items()

    # ---- Query helper ----
    def filter(self, q: str) -> List[Dict]:
        ql = (q or "").strip().lower()
        if not ql:
            return list(self.items)
        out = []
        for r in self.items:
            campos = [
                (r.get("nombre_producto") or "").lower(),
                (r.get("codigo_producto") or "").lower(),
                (r.get("descripcion_producto") or "").lower(),
                (r.get("RecID_imagen") or "").lower(),
                (r.get("ID_Imagen") or "").lower(),
                (r.get("imagen_url") or "").lower(),
            ]
            if any(ql in c for c in campos):
                out.append(r)
        return out

    # ---- Bus ----
    def _publish(self):
        if not self.bus:
            return
        try:
            self.bus.publish("items_changed", {})
        except Exception:
            pass

    # ---- CRUD ----
    def add(self, *, codigo_producto: str, nombre_producto: str,
            descripcion_producto: str = "", RecID_imagen: str = "") -> Optional[str]:
        if not self.api:
            return None
        recid = self.api.add(
            codigo_producto=codigo_producto,
            nombre_producto=nombre_producto,
            descripcion_producto=descripcion_producto,
            RecID_imagen=RecID_imagen,
        )
        self._publish()
        return recid

    def update(self, recid: str, *, codigo_producto: Optional[str] = None,
               nombre_producto: Optional[str] = None,
               descripcion_producto: Optional[str] = None,
               RecID_imagen: Optional[str] = None) -> bool:
        if not self.api:
            return False
        ok = self.api.update_by_recid(
            recid,
            codigo_producto=codigo_producto,
            nombre_producto=nombre_producto,
            descripcion_producto=descripcion_producto,
            RecID_imagen=RecID_imagen,
        )
        if ok:
            self._publish()
        return ok

    def _resolve_recid(self, recid_or_code: str) -> str:
        key = (recid_or_code or "").strip()
        if not key:
            return ""
        if key in self.item_by_recid:
            return key
        for r in self.items or []:
            if r.get("RecID") == key or r.get("codigo_producto") == key:
                return (r.get("RecID") or "").strip()
        return ""

    def delete(self, recid_or_code: str) -> bool:
        if not self.api:
            return False
        recid = self._resolve_recid(recid_or_code)
        if not recid:
            return False
        r = self.item_by_recid.get(recid, {})
        rid_img = (r.get("RecID_imagen") or r.get("ID_Imagen") or "").strip()

        if self.api_img and rid_img:
            try:
                self.api_img.delete_by_recid(rid_img)
            except Exception:
                pass

        ok = False
        tried = []

        def _try(name, *args, **kw):
            nonlocal ok, tried
            m = getattr(self.api, name, None)
            if callable(m):
                tried.append(name)
                try:
                    ok = bool(m(*args, **kw)) or ok
                except Exception:
                    pass

        _try("delete_by_recid", recid)
        if not ok:
            _try("delete", recid)
        if not ok:
            _try("delete_row_by_recid", recid)
        if not ok:
            _try("delete_where", {"RecID": recid})

        if ok:
            self.refresh_all(); self._publish()
        return ok

    def remove_image_for_item(self, recid_item: str) -> bool:
        if not self.api:
            return False
        recid_item = self._resolve_recid(recid_item)
        if not recid_item:
            return False
        r = self.item_by_recid.get(recid_item, {})
        rid_img = (r.get("RecID_imagen") or "").strip()
        ok_upd = self.api.update_by_recid(recid_item, RecID_imagen="")
        if not ok_upd:
            try:
                ok_upd = self.api.update_by_recid(recid_item, ID_Imagen="")
            except Exception:
                ok_upd = False
        ok_img = True
        if self.api_img and rid_img:
            try:
                ok_img = self.api_img.delete_by_recid(rid_img)
            except Exception:
                ok_img = False
        self.refresh_all(); self._publish()
        return bool(ok_upd and ok_img)

    # ---- Upload + attach (igual a Depósito) ----
    def upload_and_attach_image(self, recid_item: str, local_path: str,
                                folder_path: str = "TacticaGestorSheet/ImagenGestor") -> dict:
        out = {"ok": False, "recid_imagen": "", "imagen_url": "", "error": ""}
        try:
            from back.integrations.drive_user_uploader import DriveUserUploader
        except Exception:
            out["error"] = "Drive uploader no disponible"
            return out

        recid_item = self._resolve_recid(recid_item)
        local_path = (local_path or "").strip()
        if not self.api or not self.api_img:
            out["error"] = "APIs no disponibles"; return out
        if not recid_item or not local_path or not os.path.isfile(local_path):
            out["error"] = "Parámetros inválidos"; return out

        try:
            uploader = DriveUserUploader.from_page(self.page)
            file_id, view_link = uploader.upload_to_path(local_path, folder_path, make_public=True)

            recid_img = uuid4().hex[:10]
            if not self.api_img.add(recid_img, view_link):
                try: uploader.delete_file(file_id)
                except Exception: pass
                out["error"] = "No se pudo insertar en hoja 'imagen'"; return out

            ok_img_ref = self.api.update_by_recid(recid_item, RecID_imagen=recid_img)
            if not ok_img_ref:
                try:
                    ok_img_ref = self.api.update_by_recid(recid_item, ID_Imagen=recid_img)
                except Exception:
                    ok_img_ref = False
            if not ok_img_ref:
                try: self.api_img.delete_by_recid(recid_img)
                except Exception: pass
                try: uploader.delete_file(file_id)
                except Exception: pass
                out["error"] = "No se pudo actualizar 'producto.RecID_imagen'"; return out

            try: os.remove(local_path)
            except Exception: pass

            self.refresh_all(); self._publish()
            out.update({"ok": True, "recid_imagen": recid_img, "imagen_url": view_link})
            return out
        except Exception as ex:
            out["error"] = f"{ex}"; return out