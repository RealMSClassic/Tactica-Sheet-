# ./back/sheet/producto_api.py
from __future__ import annotations
from typing import Dict, List, Optional


class ItemsAPI:
    """
    CRUD directo sobre la hoja 'productos' (o 'producto').
    Normaliza el campo de imagen a 'RecID_imagen' aunque la hoja use 'RecID_Imagen' o 'ID_Imagen'.
    """

    def __init__(self, page, sheet_id: Optional[str] = None, table_name: str = "producto"):
        self.page = page
        self.sheet_id = sheet_id
        self.table_name = table_name  # cambia a "productos" si así se llama tu hoja

    # ---------- STORAGE (ajustá a tu SDK real como en deposito_api) ----------
    def _sdk(self):
        return getattr(getattr(self.page, "app_ctx", {}), "get", lambda *_: None)("sheet_sdk")

    def _storage_list(self) -> List[Dict]:
        sdk = self._sdk()
        if sdk and hasattr(sdk, "list_rows"):
            return sdk.list_rows(self.sheet_id, self.table_name)
        return []

    def _storage_add(self, row: Dict) -> Optional[str]:
        sdk = self._sdk()
        if sdk and hasattr(sdk, "insert_row"):
            return sdk.insert_row(self.sheet_id, self.table_name, row)
        return None

    def _storage_update_by_recid(self, recid: str, patch: Dict) -> bool:
        sdk = self._sdk()
        if sdk and hasattr(sdk, "update_row"):
            return bool(sdk.update_row(self.sheet_id, self.table_name, recid, patch))
        return False

    def _storage_delete_by_recid(self, recid: str) -> bool:
        sdk = self._sdk()
        if sdk and hasattr(sdk, "delete_row"):
            return bool(sdk.delete_row(self.sheet_id, self.table_name, recid))
        return False

    # ---------- Helpers ----------
    def _detect_image_key(self) -> str:
        """
        Devuelve el nombre de columna real en la hoja para el id de imagen.
        Prioriza 'RecID_imagen', luego 'RecID_Imagen', luego 'ID_Imagen'.
        """
        rows = self._storage_list()
        for r in rows:
            for k in ("RecID_imagen", "RecID_Imagen", "ID_Imagen"):
                if k in r:
                    return k
        return "RecID_imagen"

    # ---------- API pública ----------
    def list(self) -> List[Dict]:
        rows = self._storage_list()
        for r in rows:
            # Normalización hacia 'RecID_imagen'
            img = r.get("RecID_imagen") or r.get("RecID_Imagen") or r.get("ID_Imagen")
            if "RecID_imagen" not in r:
                r["RecID_imagen"] = img

            # Claves básicas
            r.setdefault("RecID", "")
            r.setdefault("codigo_producto", "")
            r.setdefault("nombre_producto", "")
            r.setdefault("descripcion_producto", "")
        return rows

    def add(
        self,
        *,
        codigo_producto: str,
        nombre_producto: str,
        descripcion_producto: str = "",
        RecID_imagen: Optional[str] = None,
    ) -> Optional[str]:
        img_key = self._detect_image_key()
        row = {
            "codigo_producto": codigo_producto,
            "nombre_producto": nombre_producto,
            "descripcion_producto": descripcion_producto,
        }
        if RecID_imagen:
            row[img_key] = RecID_imagen
        return self._storage_add(row)

    def update_by_recid(
        self,
        recid: str,
        *,
        codigo_producto: Optional[str] = None,
        nombre_producto: Optional[str] = None,
        descripcion_producto: Optional[str] = None,
        RecID_imagen: Optional[str] = None,
    ) -> bool:
        img_key = self._detect_image_key()
        patch: Dict = {}
        if codigo_producto is not None:
            patch["codigo_producto"] = codigo_producto
        if nombre_producto is not None:
            patch["nombre_producto"] = nombre_producto
        if descripcion_producto is not None:
            patch["descripcion_producto"] = descripcion_producto
        if RecID_imagen is not None:
            patch[img_key] = RecID_imagen
        if not patch:
            return True
        return self._storage_update_by_recid(recid, patch)

    def delete_by_recid(self, recid: str) -> bool:
        return self._storage_delete_by_recid(recid)
