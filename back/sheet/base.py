from __future__ import annotations
from typing import List, Dict, Optional
from back.drive.drive_check import build_sheets_service


class SheetsBase:
    """
    Base con helpers comunes para Google Sheets.
    Subclases: ProductoAPI, DepositoAPI, StockAPI.
    """
    def __init__(self, page, sheet_id: str):
        self.page = page
        self.sheet_id = sheet_id
        self.svc = build_sheets_service(page)

    # --------- helpers de bajo nivel ----------
    def _get(self, a1_range: str) -> List[List[str]]:
        resp = self.svc.spreadsheets().values().get(
            spreadsheetId=self.sheet_id, range=a1_range
        ).execute()
        return resp.get("values", []) or []

    def _set(self, a1_range: str, values: List[List[str]], input_opt: str = "USER_ENTERED"):
        body = {"values": values}
        return self.svc.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=a1_range,
            valueInputOption=input_opt,
            body=body,
        ).execute()

    def _append(self, a1_range: str, values: List[List[str]], input_opt: str = "USER_ENTERED"):
        body = {"values": values}
        return self.svc.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=a1_range,
            valueInputOption=input_opt,
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()

    def _clear(self, a1_range: str):
        return self.svc.spreadsheets().values().clear(
            spreadsheetId=self.sheet_id, range=a1_range, body={}
        ).execute()

    def _ensure_tab_and_headers(self, tab_name: str, headers: List[str]):
        """
        Crea la pestaña si no existe y escribe encabezados en la fila 1 (idempotente).
        """
        meta = self.svc.spreadsheets().get(
            spreadsheetId=self.sheet_id, fields="sheets.properties.title"
        ).execute()
        titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if tab_name not in titles:
            self.svc.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
            ).execute()
        existing = self._get(f"{tab_name}!1:1")
        if not existing or not existing[0]:
            self._set(f"{tab_name}!A1:{self._col_letter(len(headers))}1", [headers])

    @staticmethod
    def _col_letter(n: int) -> str:
        """1->A, 2->B, 26->Z, 27->AA, ..."""
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    def _find_row_by_col_value(self, tab: str, col_idx_1b: int, value: str) -> Optional[int]:
        col_letter = self._col_letter(col_idx_1b)
        values = self._get(f"{tab}!{col_letter}2:{col_letter}")  # desde fila 2
        for i, row in enumerate(values, start=2):
            v = (row[0].strip() if row and len(row) > 0 else "")
            if v == value:
                return i
        return None

    def _find_row_by_two_cols(self, tab: str, col1_idx_1b: int, val1: str, col2_idx_1b: int, val2: str) -> Optional[int]:
        """
        Busca fila por coincidencia exacta en dos columnas (1-based).
        """
        rng = f"{tab}!{self._col_letter(col1_idx_1b)}2:{self._col_letter(col2_idx_1b)}"
        rows = self._get(rng)
        for i, r in enumerate(rows, start=2):
            r = r or []
            c1 = (r[0].strip() if len(r) > 0 else "")
            offset = col2_idx_1b - col1_idx_1b
            c2 = (r[offset].strip() if len(r) > offset else "")
            if c1 == val1 and c2 == val2:
                return i
        return None

    def verify_access(self) -> Dict:
        meta = self.svc.spreadsheets().get(
            spreadsheetId=self.sheet_id, fields="properties(title)"
        ).execute()
        return meta.get("properties", {})
