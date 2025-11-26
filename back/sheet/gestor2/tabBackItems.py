# Asegurate de tener esto al tope
from __future__ import annotations
from typing import List, Dict, Optional

try:
    from back.sheet.producto_api import ProductoAPI
except Exception:
    ProductoAPI = None


class ItemsBackend:
    def __init__(self, page, bus: Optional[object] = None):
        self.page = page
        self.bus = bus
        self.sheet_id = (
            page.client_storage.get("active_sheet_id")
            or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
        )
        self.api = ProductoAPI(page, self.sheet_id) if ProductoAPI else None

        # caches SIEMPRE listas/dicts (no None)
        self.items: List[Dict] = []
        self.item_by_recid: Dict[str, Dict] = {}

    # opcional si creaste el backend sin page
    def attach_page(self, page):
        self.page = page
        self.sheet_id = (
            page.client_storage.get("active_sheet_id")
            or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
        )
        self.api = ProductoAPI(page, self.sheet_id) if ProductoAPI else None

    # -------- Refresh --------
    def refresh_items(self):
        if not self.api:
            self.items = []
            self.item_by_recid = {}
            return
        self.items = self.api.list() or []              # <- normaliza None a []
        self.item_by_recid = {r.get("RecID",""): r for r in self.items}

    def refresh_all(self):
        self.refresh_items()

    # -------- Filtro (nunca None) --------
    def filter(self, q: str) -> List[Dict]:
        data = self.items or []                         # <- evita iterar None
        ql = (q or "").strip().lower()
        if not ql:
            return list(data)
        out = []
        for d in data:
            campos = [
                (d.get("nombre_producto") or "").lower(),
                (d.get("codigo_producto") or "").lower(),
                (d.get("descripcion_producto") or "").lower(),
            ]
            if any(ql in c for c in campos):
                out.append(d)
        return out

    # -------- CRUD básicos --------
    def add(self, *, codigo_producto: str, nombre_producto: str, descripcion_producto: str = "") -> Optional[str]:
        if not self.api:
            return None
        recid = self.api.add(
            codigo_producto=codigo_producto,
            nombre_producto=nombre_producto,
            descripcion_producto=descripcion_producto,
        )
        self.refresh_items()
        self._publish()
        return recid

    def update(self, recid: str, *, codigo_producto: Optional[str] = None,
               nombre_producto: Optional[str] = None,
               descripcion_producto: Optional[str] = None) -> bool:
        if not self.api:
            return False
        ok = self.api.update_by_recid(
            recid,
            codigo_producto=codigo_producto,
            nombre_producto=nombre_producto,
            descripcion_producto=descripcion_producto,
        )
        if ok:
            self.refresh_items()
            self._publish()
        return ok

    def delete(self, recid: str) -> bool:
        if not self.api:
            return False
        ok = self.api.delete_by_recid(recid)
        if ok:
            self.refresh_items()
            self._publish()
        return ok

    # -------- Bus opcional --------
    def _publish(self):
        if not self.bus:
            return
        try:
            self.bus.publish("productos_changed", {})
        except Exception:
            pass
