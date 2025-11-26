from __future__ import annotations
from typing import List, Dict, Optional
from uuid import uuid4

from .base import SheetsBase


class StockAPI(SheetsBase):
    """
    Hoja: 'stock'
    Encabezados exactos (fila 1):
    data_ini_prox | RecID | ID_producto | ID_deposito | cantidad
    """
    TAB = "stock"
    HEADERS = ["data_ini_prox", "RecID", "ID_producto", "ID_deposito", "cantidad"]

    def _ensure(self):
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)

    def list(self) -> List[Dict]:

        self._ensure()
        rng = f"{self.TAB}!A2:{self._col_letter(len(self.HEADERS))}"
        rows = self._get(rng)
        out: List[Dict] = []
        for r in rows:
            r = (r + [""] * len(self.HEADERS))[:len(self.HEADERS)]
            rec = dict(zip(self.HEADERS, r))
            if any([rec.get("RecID"), rec.get("ID_producto"), rec.get("ID_deposito"), rec.get("cantidad")]):
                out.append({
                    "RecID": rec.get("RecID", "").strip(),                # RecID de la FILA de stock
                    "ID_producto": rec.get("ID_producto", "").strip(),    # RecID del producto
                    "ID_deposito": rec.get("ID_deposito", "").strip(),    # RecID del depósito
                    "cantidad": (rec.get("cantidad", "").strip() or "0"),
                })
        return out

    # ---------- Crear simple ----------
    def add(self, *, ID_producto: str, ID_deposito: str, cantidad: int) -> str:
        """
        Inserta una fila:
        ["", RecID_aleatorio, ID_producto, ID_deposito, cantidad]
        Reglas:
          - ID_producto / ID_deposito no vacíos (RecIDs válidos)
          - cantidad entero >= 1
        Devuelve el RecID generado (de la fila de stock).
        """
        self._ensure()
        ID_producto = (ID_producto or "").strip()
        ID_deposito = (ID_deposito or "").strip()

        try:
            cantidad = int(cantidad)
        except Exception:
            raise ValueError("La cantidad debe ser un número entero.")
        if not ID_producto or not ID_deposito:
            raise ValueError("Falta seleccionar Item y Depósito.")
        if cantidad < 1:
            raise ValueError("La cantidad debe ser un entero mayor o igual a 1.")

        recid = uuid4().hex[:10]
        self._append(
            f"{self.TAB}!A2",
            [["", recid, ID_producto, ID_deposito, str(cantidad)]],
        )
        return recid

    # ---------- Helpers lectura ----------
    def _find_row_by_prod_and_depo(self, prod_recid: str, depo_recid: str) -> Optional[int]:
        """Devuelve la fila (1-based) donde C=ID_producto y D=ID_deposito coinciden."""
        self._ensure()
        if not prod_recid or not depo_recid:
            return None
        rng = f"{self.TAB}!A2:{self._col_letter(len(self.HEADERS))}"
        rows = self._get(rng)
        for idx, r in enumerate(rows, start=2):
            r = (r + [""] * len(self.HEADERS))[:len(self.HEADERS)]
            if (r[2].strip() == prod_recid) and (r[3].strip() == depo_recid):
                return idx
        return None
    def _find_row_by_recid(self, recid_stock: str) -> Optional[int]:
        """Devuelve el número de fila (1-based) donde columna B == recid_stock."""
        recid_stock = (recid_stock or "").strip()
        if not recid_stock:
            return None
        # Columna B = 2
        return self._find_row_by_col_value(self.TAB, 2, recid_stock)

    def get_by_recid(self, recid_stock: str) -> Optional[Dict]:
        """Lee una fila de stock por RecID de la fila."""
        self._ensure()
        row = self._find_row_by_recid(recid_stock)
        if not row:
            return None
        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))
        return {
            "RecID": cur[1],
            "ID_producto": cur[2],
            "ID_deposito": cur[3],
            "cantidad": cur[4] or "0",
        }

    # ---------- Updates básicos ----------
    def update_by_recid(self, recid_stock: str, *, ID_deposito: Optional[str] = None,
                        cantidad: Optional[int] = None) -> bool:
        """
        Actualiza la fila de stock ubicada por RecID (col B).
        Si 'cantidad' es None => no cambia. Si viene valor, debe ser entero >= 0.
        Si 'ID_deposito' es None => no cambia.
        """
        self._ensure()
        row = self._find_row_by_recid(recid_stock)
        if not row:
            return False

        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))

        cur_data_ini = ""      # A siempre vacío
        cur_recid = cur[1]     # B
        cur_prod = cur[2]      # C
        cur_depo = cur[3]      # D
        cur_qty  = cur[4] or "0"   # E

        new_depo = cur_depo if ID_deposito is None else (ID_deposito or "")
        if cantidad is None:
            new_qty = cur_qty
        else:
            try:
                cantidad = int(cantidad)
            except Exception:
                return False
            if cantidad < 0:
                return False
            new_qty = str(cantidad)

        self._set(rng, [[cur_data_ini, cur_recid, cur_prod, new_depo, new_qty]])
        return True

    def add_qty(self, recid_stock: str, delta: int) -> bool:
        """Suma 'delta' a la cantidad actual (delta entero >= 1)."""
        self._ensure()
        if not isinstance(delta, int) or delta < 1:
            return False
        row = self._find_row_by_recid(recid_stock)
        if not row:
            return False
        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))
        qty = int((cur[4] or "0"))
        qty += delta
        self._set(rng, [["", cur[1], cur[2], cur[3], str(qty)]])
        return True

    def descargar(self, recid_stock: str, n: int) -> bool:
        """Resta 'n' (entero >= 1). No permite resultado negativo."""
        self._ensure()
        if not isinstance(n, int) or n < 1:
            return False
        row = self._find_row_by_recid(recid_stock)
        if not row:
            return False
        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))
        qty = int((cur[4] or "0"))
        if qty < n:
            return False
        qty -= n
        self._set(rng, [["", cur[1], cur[2], cur[3], str(qty)]])
        return True

    # ---------- Mover con nueva fila ----------
    def move_add_row(self, recid_stock_src: str, recid_deposito_dest: str, n: int) -> bool:
        """
        Mueve 'n' unidades desde la FILA fuente (recid_stock_src) hacia un depósito destino:
          - Descuenta 'n' de la fila origen.
          - Si YA existe fila (mismo ID_producto, depósito destino) => suma 'n' a ESA fila.
          - Si NO existe => crea NUEVA fila en destino con 'n'.

        Reglas:
          - n entero >= 1 y <= cantidad fuente
          - recid_deposito_dest no vacío
        """
        self._ensure()
        recid_deposito_dest = (recid_deposito_dest or "").strip()
        if not recid_deposito_dest:
            return False
        try:
            n = int(n)
        except Exception:
            return False
        if n < 1:
            return False

        # 1) Fila origen por RecID (col B)
        row_src = self._find_row_by_recid(recid_stock_src)
        if not row_src:
            return False

        rng_src = f"{self.TAB}!A{row_src}:{self._col_letter(len(self.HEADERS))}{row_src}"
        cur = (self._get(rng_src) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))

        prod_src = cur[2].strip()  # C = ID_producto
        depo_src = cur[3].strip()  # D = ID_deposito
        qty_src = int((cur[4] or "0"))

        if qty_src < n:
            return False
        if recid_deposito_dest == depo_src:
            # (el front ya lo evita, pero por seguridad)
            return False

        # 2) Descontar del origen
        qty_src_after = qty_src - n
        self._set(rng_src, [["", cur[1], prod_src, depo_src, str(qty_src_after)]])

        # 3) Buscar si ya existe fila destino para (producto, depósito destino)
        row_dest = self._find_row_by_prod_and_depo(prod_src, recid_deposito_dest)
        if row_dest:
            # Sumar a esa fila (no crear otra)
            rng_dest = f"{self.TAB}!A{row_dest}:{self._col_letter(len(self.HEADERS))}{row_dest}"
            dest = (self._get(rng_dest) or [[]])[0]
            dest += [""] * (len(self.HEADERS) - len(dest))
            qty_dest = int((dest[4] or "0"))
            qty_dest_after = qty_dest + n
            self._set(rng_dest, [["", dest[1], prod_src, recid_deposito_dest, str(qty_dest_after)]])
        else:
            # Crear NUEVA fila destino
            recid_new = uuid4().hex[:10]
            self._append(f"{self.TAB}!A2", [["", recid_new, prod_src, recid_deposito_dest, str(n)]])

        return True