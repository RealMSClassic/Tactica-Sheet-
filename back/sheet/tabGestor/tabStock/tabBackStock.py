# back/sheet/tabGestor/tabStock/tabBackStock.py
from __future__ import annotations
from typing import List, Dict, Optional

try:
    # APIs reales (opcional)
    from back.sheet.stock_api import StockAPI
    from back.sheet.producto_api import ProductoAPI
    from back.sheet.deposito_api import DepositoAPI
    from back.sheet.log_api import LogAPI, fmt_stock_move, fmt_stock_out, fmt_stock_add
except Exception:  # fallback mínimo para dev sin APIs
    StockAPI = ProductoAPI = DepositoAPI = LogAPI = None
    def fmt_stock_move(n, p, o, d): return f"[MOVE] {n} {p} {o}->{d}"
    def fmt_stock_out(n, p, d):     return f"[OUT]  {n} {p} {d}"
    def fmt_stock_add(n, p, d):     return f"[ADD]  {n} {p} {d}"


class StockBackend:
    """
    Backend para pestaña Stock.
    - Si se pasan items_backend / depo_backend, reutiliza sus listas y mapas.
    - Si no, intenta usar ProductoAPI / DepositoAPI / StockAPI.
    Expone:
      refresh_all / refresh_products / refresh_depositos / refresh_stock
      filter_grouped_by_product / filter_grouped_by_deposito
      rows_for_product / rows_for_deposito
      add_new_stock / add_qty / descargar / move_add_row
      safe_int
    """

    def __init__(
        self,
        page,
        bus: Optional[object] = None,
        depo_backend: Optional[object] = None,
        items_backend: Optional[object] = None,
    ):
        self.page = page
        self.bus = bus
        self.depo_backend = depo_backend
        self.items_backend = items_backend

        # Para uso de APIs como fallback
        self.sheet_id = (
            page.client_storage.get("active_sheet_id")
            or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
        )

        self.api_stock = StockAPI(page, self.sheet_id) if StockAPI else None
        self.api_prod  = ProductoAPI(page, self.sheet_id) if ProductoAPI else None
        self.api_depo  = DepositoAPI(page, self.sheet_id) if DepositoAPI else None
        self.logger    = LogAPI(page, self.sheet_id)      if LogAPI else None

        # caches
        self.productos: List[Dict] = []
        self.depositos: List[Dict] = []
        self.stock_rows: List[Dict] = []

        self.prod_by_recid: Dict[str, Dict] = {}
        self.depo_by_recid: Dict[str, Dict] = {}

    # ---------- Utils ----------
    def attach_page(self, page):
        self.page = page

    @staticmethod
    def safe_int(v) -> int:
        try:
            return int(str(v).strip() or "0")
        except Exception:
            return 0

    # ---------- Refresh ----------
    def refresh_products(self):
        # 1) Reutiliza items_backend si está conectado
        if self.items_backend and getattr(self.items_backend, "productos", None):
            self.productos = list(self.items_backend.productos or [])
            self.prod_by_recid = dict(self.items_backend.prod_by_recid or {})
            return
        # 2) Fallback a API
        if not self.api_prod:
            self.productos = []
            self.prod_by_recid = {}
            return
        self.productos = self.api_prod.list() or []
        self.prod_by_recid = {p.get("RecID", ""): p for p in self.productos}

    def refresh_depositos(self):
        # 1) Reutiliza depo_backend si está conectado
        if self.depo_backend and getattr(self.depo_backend, "depositos", None):
            self.depositos = list(self.depo_backend.depositos or [])
            self.depo_by_recid = dict(self.depo_backend.depo_by_recid or {})
            return
        # 2) Fallback a API
        if not self.api_depo:
            self.depositos = []
            self.depo_by_recid = {}
            return
        self.depositos = self.api_depo.list() or []
        self.depo_by_recid = {d.get("RecID", ""): d for d in self.depositos}

    def refresh_stock(self):
        if not self.api_stock:
            self.stock_rows = []
            return
        self.stock_rows = self.api_stock.list() or []

    def refresh_all(self):
        self.refresh_products()
        self.refresh_depositos()
        self.refresh_stock()

    # ---------- Grouping ----------
    def _aggregate_by_product(self, rows: List[Dict]) -> List[Dict]:
        rows = rows or []
        agg: Dict[str, int] = {}
        for r in rows:
            pid = r.get("ID_producto", "")
            if not pid:
                continue
            agg[pid] = agg.get(pid, 0) + self.safe_int(r.get("cantidad", 0))
        return [{"ID_producto": k, "total": v} for k, v in agg.items()]

    def _aggregate_by_deposito(self, rows: List[Dict]) -> List[Dict]:
        rows = rows or []
        agg: Dict[str, int] = {}
        for r in rows:
            did = r.get("ID_deposito", "")
            if not did:
                continue
            agg[did] = agg.get(did, 0) + self.safe_int(r.get("cantidad", 0))
        return [{"ID_deposito": k, "total": v} for k, v in agg.items()]

    # ---------- Filters for UI ----------
    def filter_grouped_by_product(self, q: str) -> List[Dict]:
        grouped = self._aggregate_by_product(self.stock_rows or [])
        if not q:
            return grouped
        out = []
        ql = q.lower()
        for g in grouped:
            p = self.prod_by_recid.get(g["ID_producto"], {}) or {}
            campos = [
                (p.get("nombre_producto") or "").lower(),
                (p.get("codigo_producto") or "").lower(),
            ]
            if any(ql in c for c in campos):
                out.append(g)
        return out

    def filter_grouped_by_deposito(self, q: str) -> List[Dict]:
        grouped = self._aggregate_by_deposito(self.stock_rows or [])
        if not q:
            return grouped
        out = []
        ql = q.lower()
        for g in grouped:
            d = self.depo_by_recid.get(g["ID_deposito"], {}) or {}
            campos = [
                (d.get("nombre_deposito") or "").lower(),
                (d.get("id_deposito") or "").lower(),
            ]
            if any(ql in c for c in campos):
                out.append(g)
        return out

    def rows_for_product(self, prod_recid: str) -> List[Dict]:
        rows = self.stock_rows or []
        return [
            r for r in rows
            if r.get("ID_producto") == prod_recid and self.safe_int(r.get("cantidad", 0)) > 0
        ]

    def rows_for_deposito(self, depo_recid: str) -> List[Dict]:
        rows = self.stock_rows or []
        return [
            r for r in rows
            if r.get("ID_deposito") == depo_recid and self.safe_int(r.get("cantidad", 0)) > 0
        ]

    # ---------- Bus helper ----------
    def _publish(self, topic: str, payload: Optional[dict] = None):
        if not self.bus:
            return
        try:
            self.bus.publish(topic, payload or {})
        except Exception:
            pass

    # ---------- Actions ----------
    def add_new_stock(self, item_recid: str, depo_recid: str, qty: int,
                      product_name: str = "", depo_name: str = "") -> Optional[str]:
        if not self.api_stock:
            return None
        recid = self.api_stock.add(ID_producto=item_recid, ID_deposito=depo_recid, cantidad=qty)
        try:
            if self.logger:
                self.logger.append(fmt_stock_add(qty, product_name or "(producto)", depo_name or "(depósito)"))
        except Exception:
            pass
        self._publish("stock_changed", {"op": "add_new", "recid": recid})
        return recid

    def add_qty(self, recid_stock: str, delta: int,
                product_name: str = "", depo_name: str = "") -> bool:
        if not self.api_stock:
            return False
        ok = self.api_stock.add_qty(recid_stock, delta)
        if ok:
            try:
                if self.logger:
                    self.logger.append(fmt_stock_add(delta, product_name or "(producto)", depo_name or "(depósito)"))
            except Exception:
                pass
            self._publish("stock_changed", {"op": "add_qty", "recid": recid_stock, "delta": delta})
        return ok

    def descargar(self, recid_stock: str, n: int,
                  product_name: str = "", depo_name: str = "") -> bool:
        if not self.api_stock:
            return False
        ok = self.api_stock.descargar(recid_stock, n)
        if ok:
            try:
                if self.logger:
                    self.logger.append(fmt_stock_out(n, product_name or "(producto)", depo_name or "(depósito)"))
            except Exception:
                pass
            self._publish("stock_changed", {"op": "descargar", "recid": recid_stock, "n": n})
        return ok

    def move_add_row(self, recid_stock_src: str, recid_deposito_dest: str, n: int,
                     product_name: str = "", origin_name: str = "", dest_name: str = "") -> bool:
        if not self.api_stock:
            return False
        ok = self.api_stock.move_add_row(recid_stock_src, recid_deposito_dest, n)
        if ok:
            try:
                if self.logger:
                    self.logger.append(
                        fmt_stock_move(n, product_name or "(producto)", origin_name or "(origen)", dest_name or "(destino)")
                    )
            except Exception:
                pass
            self._publish("stock_changed", {
                "op": "move_add_row",
                "recid_src": recid_stock_src,
                "recid_dest": recid_deposito_dest,
                "n": n
            })
        return ok
