from __future__ import annotations
from typing import List, Dict, Optional
from uuid import uuid4
from .base import SheetsBase


class DepositoAPI(SheetsBase):
    """
    Hoja: 'deposito'
    Encabezados exactos (fila 1):
    data_ini_prox | RecID | id_deposito | nombre_deposito | direccion_deposito | descripcion_deposito | RecID_imagen
    """
    TAB = "deposito"
    HEADERS = [
        "data_ini_prox", "RecID", "id_deposito", "nombre_deposito",
        "direccion_deposito", "descripcion_deposito", "RecID_imagen"  # <-- agregado
    ]

    def list(self) -> List[Dict]:
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)
        rng = f"{self.TAB}!A2:{self._col_letter(len(self.HEADERS))}"
        rows = self._get(rng)
        out = []
        for r in rows:
            r = (r + [""] * len(self.HEADERS))[:len(self.HEADERS)]
            rec = dict(zip(self.HEADERS, r))
            if any((
                rec.get("RecID"), rec.get("id_deposito"), rec.get("nombre_deposito"),
                rec.get("direccion_deposito"), rec.get("descripcion_deposito"), rec.get("RecID_imagen")
            )):
                out.append({
                    "RecID": rec.get("RecID", "").strip(),
                    "id_deposito": rec.get("id_deposito", "").strip(),
                    "nombre_deposito": rec.get("nombre_deposito", "").strip(),
                    "direccion_deposito": rec.get("direccion_deposito", "").strip(),
                    "descripcion_deposito": rec.get("descripcion_deposito", "").strip(),
                    "RecID_imagen": rec.get("RecID_imagen", "").strip(),   # <-- expuesto
                })
        return out

    def add(self, *, id_deposito: str, nombre_deposito: str,
            direccion_deposito: str = "", descripcion_deposito: str = "", RecID_imagen: str = "") -> str:
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)
        recid = uuid4().hex[:10]
        self._append(
            f"{self.TAB}!A2",
            [[
                "", recid,
                (id_deposito or "").strip(),
                (nombre_deposito or "").strip(),
                (direccion_deposito or "").strip(),
                (descripcion_deposito or "").strip(),
                (RecID_imagen or "").strip(),
            ]]
        )
        return recid

    def update_by_recid(self, recid: str, *,
                        id_deposito: Optional[str] = None, nombre_deposito: Optional[str] = None,
                        direccion_deposito: Optional[str] = None, descripcion_deposito: Optional[str] = None,
                        RecID_imagen: Optional[str] = None) -> bool:
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)
        recid = (recid or "").strip()
        if not recid:
            return False
        row = self._find_row_by_col_value(self.TAB, 2, recid)  # B=RecID
        if not row:
            return False
        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))
        cur[0] = ""  # data_ini_prox
        if id_deposito is not None:      cur[2] = (id_deposito or "")
        if nombre_deposito is not None:  cur[3] = (nombre_deposito or "")
        if direccion_deposito is not None: cur[4] = (direccion_deposito or "")
        if descripcion_deposito is not None: cur[5] = (descripcion_deposito or "")
        if RecID_imagen is not None:     cur[6] = (RecID_imagen or "")
        self._set(rng, [cur])
        return True

    def delete_by_recid(self, recid: str) -> bool:
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)
        recid = (recid or "").strip()
        if not recid:
            return False
        row = self._find_row_by_col_value(self.TAB, 2, recid)  # B=RecID
        if not row:
            return False
        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        self._clear(rng)
        return True
