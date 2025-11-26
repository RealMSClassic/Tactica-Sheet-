from __future__ import annotations
from typing import List, Dict, Optional
from .base import SheetsBase


class ImagenAPI(SheetsBase):
    """
    Hoja: 'imagen'
    Encabezados exactos (fila 1):
    data_ini_prox | RecID | ID_nombre
    """
    TAB = "imagen"
    HEADERS = ["data_ini_prox", "RecID", "ID_nombre"]
    def add(self, recid: str, link: str) -> bool:
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)
        recid = (recid or "").strip()
        link = (link or "").strip()
        if not recid or not link: 
            return False
        self._append(f"{self.TAB}!A2", [[ "", recid, link ]])
        return True
    def list(self) -> List[Dict]:
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)
        rng = f"{self.TAB}!A2:{self._col_letter(len(self.HEADERS))}"
        rows = self._get(rng)
        out: List[Dict] = []
        for r in rows:
            r = (r + [""] * len(self.HEADERS))[:len(self.HEADERS)]
            rec = dict(zip(self.HEADERS, r))
            if any((rec.get("RecID"), rec.get("ID_nombre"))):
                out.append({
                    "RecID": (rec.get("RecID") or "").strip(),
                    "ID_nombre": (rec.get("ID_nombre") or "").strip(),
                })
        return out

    def get_link_by_recid(self, recid: str) -> Optional[str]:
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)
        recid = (recid or "").strip()
        if not recid:
            return None
        row = self._find_row_by_col_value(self.TAB, 2, recid)  # B=RecID
        if not row:
            return None
        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))
        return (cur[2] or "").strip()  # C = ID_nombre (link)

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
