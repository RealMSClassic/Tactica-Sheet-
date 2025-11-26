# ./back/sheet/gestor/tabBackDeposito.py
from __future__ import annotations
from typing import List, Dict, Optional

try:
    from back.sheet.deposito_api import DepositoAPI
except Exception:
    DepositoAPI = None


class DepositoBackend:
    """
    Backend para Depósitos. Expone helpers para el front:
      - refresh_all / refresh_depositos
      - filter(q)
      - add / update / delete
      - mapas: depo_by_recid
    Publica en bus (opcional) el tópico "depositos_changed".
    """

    def __init__(self, page=None, bus: Optional[object] = None):
        self.page = page
        self.bus = bus

        # Si tu app guarda el Sheet ID en client_storage o contexto, podés leerlo aquí.
        self.sheet_id = None
        if page is not None:
            self.sheet_id = (
                page.client_storage.get("active_sheet_id")
                or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
            )

        self.api = DepositoAPI(page, self.sheet_id) if (DepositoAPI and page is not None) else None

        self.depositos: List[Dict] = []
        self.depo_by_recid: Dict[str, Dict] = {}

    # -------- Opcional: si querés poder inyectar page luego ----------
    def attach_page(self, page):
        self.page = page
        self.sheet_id = (
            page.client_storage.get("active_sheet_id")
            or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
        )
        self.api = DepositoAPI(page, self.sheet_id) if DepositoAPI else None

    # -------- Refresh ----------
    def refresh_depositos(self):
        if not self.api:
            self.depositos = []
            self.depo_by_recid = {}
            return
        self.depositos = self.api.list()
        self.depo_by_recid = {d.get("RecID", ""): d for d in self.depositos}

    def refresh_all(self):
        self.refresh_depositos()

    # -------- Query helpers ----------
    def filter(self, q: str) -> List[Dict]:
        ql = (q or "").strip().lower()
        if not ql:
            return list(self.depositos)
        out = []
        for d in self.depositos:
            campos = [
                (d.get("nombre_deposito") or "").lower(),
                (d.get("id_deposito") or "").lower(),
                (d.get("direccion_deposito") or "").lower(),
                (d.get("descripcion_deposito") or "").lower(),
            ]
            if any(ql in c for c in campos):
                out.append(d)
        return out

    # -------- Bus ----------
    def _publish(self):
        if not self.bus:
            return
        try:
            self.bus.publish("depositos_changed", {})
        except Exception:
            pass

    # -------- CRUD ----------
    def add(self, *, id_deposito: str, nombre_deposito: str,
            direccion_deposito: str = "", descripcion_deposito: str = "") -> Optional[str]:
        if not self.api:
            return None
        recid = self.api.add(
            id_deposito=id_deposito,
            nombre_deposito=nombre_deposito,
            direccion_deposito=direccion_deposito,
            descripcion_deposito=descripcion_deposito,
        )
        self._publish()
        return recid

    def update(self, recid: str, *, id_deposito: Optional[str] = None,
               nombre_deposito: Optional[str] = None,
               direccion_deposito: Optional[str] = None,
               descripcion_deposito: Optional[str] = None) -> bool:
        if not self.api:
            return False
        ok = self.api.update_by_recid(
            recid,
            id_deposito=id_deposito,
            nombre_deposito=nombre_deposito,
            direccion_deposito=direccion_deposito,
            descripcion_deposito=descripcion_deposito,
        )
        if ok:
            self._publish()
        return ok

    def delete(self, recid: str) -> bool:
        if not self.api:
            return False
        ok = self.api.delete_by_recid(recid)
        if ok:
            self._publish()
        return ok
