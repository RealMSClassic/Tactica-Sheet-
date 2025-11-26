# back/sheets_api.py
from __future__ import annotations
from typing import List, Dict, Optional
from datetime import datetime
from uuid import uuid4

from back.drive.drive_check import build_sheets_service


class SheetsAPI:
    """
    Fachada simple para leer/escribir en un Spreadsheet de Google.
    Usa `build_sheets_service(page)` y el `sheet_id` activo.
    Incluye métodos de dominio para: Items/Producto (configurable), Depósitos (legacy),
    Stock, Usuarios, Log.

    Config para trabajar con una pestaña arbitraria (p. ej., "producto" o "deposito"):
      - items_tab_name   -> nombre de la pestaña
      - items_headers    -> encabezados EXACTOS de la fila 1
      - items_fieldnames -> claves que expondrá list_items() (subset/igual a headers)

    Ejemplo para hoja 'producto':
      items_tab_name   = "producto"
      items_headers    = ["data_ini_prox", "RecID", "codigo_producto", "nombre_producto", "descripcion_producto"]
      items_fieldnames = ["RecID", "codigo_producto", "nombre_producto", "descripcion_producto"]

    Ejemplo para hoja 'deposito':
      items_tab_name   = "deposito"
      items_headers    = ["data_ini_prox", "RecID", "id_deposito", "nombre_deposito", "direccion_deposito", "descripcion_deposito"]
      items_fieldnames = ["RecID", "id_deposito", "nombre_deposito", "direccion_deposito", "descripcion_deposito"]
    """

    # --- Defaults legacy (retrocompatibilidad) ---
    ITEMS_TAB = "Items"
    ITEMS_HEADERS = ["Nombre", "Codigo", "Descripcion"]
    ITEMS_FIELDNAMES = ["nombre", "codigo", "descripcion"]  # lo que expone la API por defecto

    DEPOS_TAB = "Deposito"
    DEPOS_HEADERS = ["Nombre", "ID", "Direccion", "Descripcion"]

    # --- Stock (actual) ---
    STOCK_TAB = "stock"
    STOCK_HEADERS = ["data_ini_prox", "RecID", "recid_producto", "recid_deposito", "cantidad"]

    USERS_TAB = "Usuarios"
    USERS_HEADERS = ["Nombre", "Correo", "Rango"]  # Rango: Administrador/Editor/Visitante

    LOG_TAB = "Log"
    LOG_HEADERS = ["Fecha", "Usuario", "Accion"]

    def __init__(
        self,
        page,
        sheet_id: str,
        *,
        items_tab_name: Optional[str] = None,
        items_headers: Optional[List[str]] = None,
        items_fieldnames: Optional[List[str]] = None,
    ):
        self.page = page
        self.sheet_id = sheet_id
        self.svc = build_sheets_service(page)

        # Config de Items/Producto/Deposito con defaults retro-compatibles
        self.items_tab_name: str = items_tab_name or self.ITEMS_TAB
        self.items_headers: List[str] = list(items_headers or self.ITEMS_HEADERS)
        self.items_fieldnames: List[str] = list(items_fieldnames or self.ITEMS_FIELDNAMES)

        if not self.items_headers:
            self.items_headers = list(self.ITEMS_HEADERS)
        if not self.items_fieldnames:
            self.items_fieldnames = list(self.ITEMS_FIELDNAMES)

    # ---------------------------------------------------------------------
    # Utilitarios base
    # ---------------------------------------------------------------------
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
        needs_create = tab_name not in titles

        if needs_create:
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

    def _find_row_by_col_value(self, tab: str, col_idx: int, value: str) -> Optional[int]:
        """
        Busca una fila por valor exacto en la columna `col_idx` (1-based).
        Devuelve el número de fila (1-based). Considera headers en fila 1.
        """
        col_letter = self._col_letter(col_idx)
        values = self._get(f"{tab}!{col_letter}2:{col_letter}")  # desde fila 2
        for i, row in enumerate(values, start=2):
            v = (row[0].strip() if row and len(row) > 0 else "")
            if v == value:
                return i
        return None

    # ------- Helpers Stock -------
    def _ensure_stock(self):
        self._ensure_tab_and_headers(self.STOCK_TAB, self.STOCK_HEADERS)

    def _find_row_by_two_cols(self, tab: str, col1_idx: int, val1: str, col2_idx: int, val2: str) -> Optional[int]:
        """
        Busca fila por coincidencia exacta en dos columnas (1-based).
        """
        rng = f"{tab}!{self._col_letter(col1_idx)}2:{self._col_letter(col2_idx)}"
        rows = self._get(rng)
        for i, r in enumerate(rows, start=2):
            r = r or []
            c1 = (r[0].strip() if len(r) > 0 else "")
            offset = col2_idx - col1_idx
            c2 = (r[offset].strip() if len(r) > offset else "")
            if c1 == val1 and c2 == val2:
                return i
        return None

    def verify_access(self) -> Dict:
        """Devuelve metadata mínima del sheet (p. ej., título)."""
        meta = self.svc.spreadsheets().get(
            spreadsheetId=self.sheet_id, fields="properties(title)"
        ).execute()
        return meta.get("properties", {})

    # ---------------------------------------------------------------------
    # ITEMS (configurable: puede ser 'Items' legacy, 'producto' o 'deposito')
    # ---------------------------------------------------------------------
    def list_items(self) -> List[Dict]:
        """
        Devuelve una lista de dicts con claves = self.items_fieldnames.
        Funciona para 'producto', 'deposito' o 'Items' legacy (mapeo básico).
        """
        tab = self.items_tab_name
        headers = self.items_headers
        self._ensure_tab_and_headers(tab, headers)

        rng = f"{tab}!A2:{self._col_letter(len(headers))}"
        rows = self._get(rng)

        out: List[Dict] = []
        for r in rows:
            # Normaliza largo según headers
            row = (r + [""] * max(0, (len(headers) - len(r))))[:len(headers)]
            item = dict(zip(headers, row))  # por nombres de encabezados

            # Exponer con fieldnames
            exposed: Dict[str, str] = {}
            for fname in self.items_fieldnames:
                if fname in headers:
                    exposed[fname] = (item.get(fname, "") or "").strip()
                else:
                    # Mapeo legacy -> fieldnames (solo Items clásico)
                    if fname == "nombre" and "Nombre" in headers:
                        exposed[fname] = (item.get("Nombre", "") or "").strip()
                    elif fname == "codigo" and "Codigo" in headers:
                        exposed[fname] = (item.get("Codigo", "") or "").strip()
                    elif fname == "descripcion" and "Descripcion" in headers:
                        exposed[fname] = (item.get("Descripcion", "") or "").strip()
                    else:
                        exposed[fname] = ""
            if any(v for v in exposed.values()):
                out.append(exposed)
        return out

    def add_item(self, nombre: Optional[str] = None, codigo: Optional[str] = None,
                 descripcion: str = "", **kwargs):
        """
        Inserta una fila respetando el layout configurado en `items_headers`.
        Soporta:
          - deposito:  ["data_ini_prox","RecID","id_deposito","nombre_deposito","direccion_deposito","descripcion_deposito"]
          - producto:  ["data_ini_prox","RecID","codigo_producto","nombre_producto","descripcion_producto"]
          - legacy:    ["Nombre","Codigo","Descripcion"]
        """
        tab = self.items_tab_name
        headers = self.items_headers
        self._ensure_tab_and_headers(tab, headers)

        # ---- MODO DEPOSITO (A..F) ----
        deposito_mode = (
            len(headers) == 6 and
            headers[0] == "data_ini_prox" and
            headers[1] == "RecID" and
            headers[2] == "id_deposito" and
            headers[3] == "nombre_deposito" and
            headers[4] == "direccion_deposito" and
            headers[5] == "descripcion_deposito"
        )
        if deposito_mode:
            recid = (kwargs.get("RecID") or kwargs.get("recid") or uuid4().hex[:10])
            id_deposito = (kwargs.get("id_deposito") or "").strip()
            nombre_deposito = (kwargs.get("nombre_deposito") or "").strip()
            direccion_deposito = (kwargs.get("direccion_deposito") or "").strip()
            descripcion_deposito = (kwargs.get("descripcion_deposito") or "").strip()
            self._append(
                f"{tab}!A2",
                [["", recid, id_deposito, nombre_deposito, direccion_deposito, descripcion_deposito]]
            )
            return

        # ---- MODO PRODUCTO (A..E) ----
        producto_mode = (
            len(headers) == 5 and
            headers[0] == "data_ini_prox" and
            headers[1] == "RecID" and
            headers[2] == "codigo_producto" and
            headers[3] == "nombre_producto" and
            headers[4] == "descripcion_producto"
        )
        if producto_mode:
            codigo_producto = (kwargs.get("codigo_producto") or codigo or "").strip()
            nombre_producto = (kwargs.get("nombre_producto") or nombre or "").strip()
            descripcion_producto = (kwargs.get("descripcion_producto") or descripcion or "").strip()
            recid = (kwargs.get("RecID") or kwargs.get("recid") or uuid4().hex[:10])
            self._append(
                f"{tab}!A2",
                [["", recid, codigo_producto, nombre_producto, descripcion_producto]]
            )
            return

        # ---- Legacy Items ----
        nombre_v = (nombre or kwargs.get("nombre", "")).strip()
        codigo_v = (codigo or kwargs.get("codigo", "")).strip()
        descripcion_v = (descripcion or kwargs.get("descripcion", "")).strip()
        self._append(f"{tab}!A2", [[nombre_v, codigo_v, descripcion_v]])

    def update_item_by_recid(self, recid: str, **kwargs) -> bool:
        """
        Actualiza una fila por RecID (columna 'RecID') en la pestaña configurada.
        - No modifica 'RecID'.
        - Si existe 'data_ini_prox', la deja en blanco.
        - Solo actualiza las columnas presentes en kwargs y cuyo valor no sea None.
        Sirve para 'producto' y 'deposito'.
        """
        tab = self.items_tab_name
        headers = self.items_headers
        self._ensure_tab_and_headers(tab, headers)

        recid = (recid or "").strip()
        if not recid or "RecID" not in headers:
            return False

        rec_idx_1b = headers.index("RecID") + 1  # 1-based
        row = self._find_row_by_col_value(tab, rec_idx_1b, recid)
        if not row:
            return False

        rng = f"{tab}!A{row}:{self._col_letter(len(headers))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(headers) - len(cur))

        new_row = cur[:]
        for k, v in kwargs.items():
            if v is None:
                continue
            if k in headers and k != "RecID":
                new_row[headers.index(k)] = v

        # A=data_ini_prox vacío si existe
        if "data_ini_prox" in headers:
            new_row[headers.index("data_ini_prox")] = ""

        self._set(rng, [new_row])
        return True

    def delete_item_by_recid(self, recid: str) -> bool:
        """
        Borra una fila buscando por RecID en la pestaña configurada.
        Sirve para 'producto' y 'deposito'.
        """
        tab = self.items_tab_name
        headers = self.items_headers
        self._ensure_tab_and_headers(tab, headers)

        recid = (recid or "").strip()
        if not recid or "RecID" not in headers:
            return False

        rec_idx_1b = headers.index("RecID") + 1
        row = self._find_row_by_col_value(tab, rec_idx_1b, recid)
        if not row:
            return False

        rng = f"{tab}!A{row}:{self._col_letter(len(headers))}{row}"
        self._clear(rng)
        return True

    def update_item_by_codigo(self, codigo: Optional[str] = None, *,
                              nombre: Optional[str] = None,
                              descripcion: Optional[str] = None,
                              **kwargs) -> bool:
        """
        Actualiza por código (clave de item).
        - Producto: usa 'codigo_producto' en headers y respeta 'data_ini_prox' vacío.
        - Legacy:   usa 'Codigo' en hoja 'Items'.
        """
        tab = self.items_tab_name
        headers = self.items_headers
        self._ensure_tab_and_headers(tab, headers)

        # --- Producto (con data_ini_prox) ---
        if "codigo_producto" in headers:
            codigo_clave = (kwargs.get("codigo_producto") or codigo or "").strip()
            if not codigo_clave:
                return False
            col_idx = headers.index("codigo_producto") + 1  # 1-based
            row = self._find_row_by_col_value(tab, col_idx, codigo_clave)
            if not row:
                return False

            rng = f"{tab}!A{row}:{self._col_letter(len(headers))}{row}"
            cur = (self._get(rng) or [[]])[0]
            cur += [""] * (len(headers) - len(cur))

            new_row = cur[:]
            # No tocar RecID ni codigo_producto (clave)
            v_nombre = kwargs.get("nombre_producto")
            if v_nombre is None:
                v_nombre = nombre
            if v_nombre is not None and "nombre_producto" in headers:
                new_row[headers.index("nombre_producto")] = v_nombre

            v_desc = kwargs.get("descripcion_producto")
            if v_desc is None:
                v_desc = descripcion
            if v_desc is not None and "descripcion_producto" in headers:
                new_row[headers.index("descripcion_producto")] = v_desc

            if "data_ini_prox" in headers:
                new_row[headers.index("data_ini_prox")] = ""

            self._set(rng, [new_row])
            return True

        # --- Legacy Items ---
        codigo_clave = (codigo or "").strip()
        if not codigo_clave:
            return False
        # col 2 = "Codigo"
        row = self._find_row_by_col_value(tab, 2, codigo_clave)
        if not row:
            return False
        rng = f"{tab}!A{row}:{self._col_letter(len(headers))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(headers) - len(cur))

        new_nombre = nombre if nombre is not None else cur[0]
        new_codigo = cur[1]  # no cambiamos clave
        new_desc = descripcion if descripcion is not None else cur[2]
        self._set(rng, [[new_nombre, new_codigo, new_desc]])
        return True

    def delete_item_by_codigo(self, codigo: Optional[str] = None, **kwargs) -> bool:
        """
        Borra por código (clave de item).
        - Producto: 'codigo_producto'
        - Legacy:   'Codigo'
        """
        tab = self.items_tab_name
        headers = self.items_headers
        self._ensure_tab_and_headers(tab, headers)

        # --- Producto ---
        if "codigo_producto" in headers:
            codigo_clave = (kwargs.get("codigo_producto") or codigo or "").strip()
            if not codigo_clave:
                return False
            col_idx = headers.index("codigo_producto") + 1  # 1-based
            row = self._find_row_by_col_value(tab, col_idx, codigo_clave)
            if not row:
                return False
            rng = f"{tab}!A{row}:{self._col_letter(len(headers))}{row}"
            self._clear(rng)
            return True

        # --- Legacy Items ---
        codigo_clave = (codigo or "").strip()
        if not codigo_clave:
            return False
        row = self._find_row_by_col_value(tab, 2, codigo_clave)
        if not row:
            return False
        rng = f"{tab}!A{row}:{self._col_letter(len(headers))}{row}"
        self._clear(rng)
        return True

    # ---------------------------------------------------------------------
    # STOCK (hoja: stock | A:data_ini_prox B:RecID C:recid_producto D:recid_deposito E:cantidad)
    # ---------------------------------------------------------------------
    def stock_list_by_producto(self, recid_producto: str) -> List[Dict]:
        """
        Devuelve las filas de stock para un producto por depósito:
        [{"recid_deposito": "...", "cantidad": "10"}, ...]
        """
        self._ensure_stock()
        recid_producto = (recid_producto or "").strip()
        if not recid_producto:
            return []
        rng = f"{self.STOCK_TAB}!A2:{self._col_letter(len(self.STOCK_HEADERS))}"
        rows = self._get(rng)
        out = []
        for r in rows:
            r += [""] * (len(self.STOCK_HEADERS) - len(r))
            c_prod = (r[2] or "").strip()
            c_dep  = (r[3] or "").strip()
            cant   = (r[4] or "0").strip()
            if c_prod == recid_producto and (c_dep or cant):
                out.append({"recid_deposito": c_dep, "cantidad": cant})
        return out

    def stock_add(self, recid_producto: str, recid_deposito: str, cantidad: int) -> bool:
        """
        Suma 'cantidad' (positiva) al stock del par (producto, depósito).
        Crea la fila si no existe. Mantiene A vacío y genera RecID si crea.
        """
        self._ensure_stock()
        recid_producto = (recid_producto or "").strip()
        recid_deposito = (recid_deposito or "").strip()
        try:
            cantidad = int(cantidad)
        except Exception:
            return False
        if not recid_producto or not recid_deposito or cantidad <= 0:
            return False

        # buscar fila por (C=recid_producto, D=recid_deposito)
        row = self._find_row_by_two_cols(self.STOCK_TAB, 3, recid_producto, 4, recid_deposito)
        if not row:
            recid = uuid4().hex[:10]
            self._append(f"{self.STOCK_TAB}!A2", [["", recid, recid_producto, recid_deposito, str(cantidad)]])
            return True

        rng = f"{self.STOCK_TAB}!A{row}:{self._col_letter(len(self.STOCK_HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.STOCK_HEADERS) - len(cur))
        cur[0] = ""  # data_ini_prox
        old = int((cur[4] or "0").strip() or 0)
        cur[4] = str(old + cantidad)
        self._set(rng, [cur])
        return True

    def stock_descargar(self, recid_producto: str, recid_deposito: str, cantidad: int) -> bool:
        """
        Resta 'cantidad' (positiva) al stock del par (producto, depósito).
        No permite cantidades negativas.
        """
        self._ensure_stock()
        recid_producto = (recid_producto or "").strip()
        recid_deposito = (recid_deposito or "").strip()
        try:
            cantidad = int(cantidad)
        except Exception:
            return False
        if not recid_producto or not recid_deposito or cantidad <= 0:
            return False

        row = self._find_row_by_two_cols(self.STOCK_TAB, 3, recid_producto, 4, recid_deposito)
        if not row:
            return False
        rng = f"{self.STOCK_TAB}!A{row}:{self._col_letter(len(self.STOCK_HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.STOCK_HEADERS) - len(cur))
        cur[0] = ""  # data_ini_prox
        old = int((cur[4] or "0").strip() or 0)
        newv = old - cantidad
        if newv < 0:
            return False
        cur[4] = str(newv)
        self._set(rng, [cur])
        return True

    def stock_move(self, recid_producto: str, recid_deposito_from: str, recid_deposito_to: str, cantidad: int) -> bool:
        """
        Mueve 'cantidad' del depósito origen al destino.
        """
        try:
            cantidad = int(cantidad)
        except Exception:
            return False
        if not recid_producto or not recid_deposito_from or not recid_deposito_to or cantidad <= 0:
            return False
        if recid_deposito_from == recid_deposito_to:
            return False
        # descargar origen
        if not self.stock_descargar(recid_producto, recid_deposito_from, cantidad):
            return False
        # agregar destino
        return self.stock_add(recid_producto, recid_deposito_to, cantidad)

    # ---------------------------------------------------------------------
    # DEPOSITO (legacy) — se mantiene para compatibilidad con proyectos viejos
    # ---------------------------------------------------------------------
    def list_depositos(self) -> List[Dict]:
        self._ensure_tab_and_headers(self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB, self.DEPOS_HEADERS)
        tab = self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB
        rng = f"{tab}!A2:{self._col_letter(len(self.DEPOS_HEADERS))}"
        rows = self._get(rng)
        out = []
        for r in rows:
            nombre = (r[0].strip() if len(r) > 0 else "")
            did = (r[1].strip() if len(r) > 1 else "")
            dir_ = (r[2].strip() if len(r) > 2 else "")
            desc = (r[3].strip() if len(r) > 3 else "")
            if any([nombre, did, dir_, desc]):
                out.append({"nombre": nombre, "id": did, "direccion": dir_, "descripcion": desc})
        return out

    def add_deposito(self, nombre: str, did: str, direccion: str = "", descripcion: str = ""):
        self._ensure_tab_and_headers(self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB, self.DEPOS_HEADERS)
        tab = self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB
        self._append(f"{tab}!A2", [[nombre, did, direccion, descripcion]])

    def update_deposito_by_id(self, did: str, *, nombre: Optional[str] = None,
                              direccion: Optional[str] = None, descripcion: Optional[str] = None) -> bool:
        self._ensure_tab_and_headers(self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB, self.DEPOS_HEADERS)
        tab = self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB
        row = self._find_row_by_col_value(tab, 2, did)  # col 2 = ID
        if not row:
            return False
        rng = f"{tab}!A{row}:{self._col_letter(len(self.DEPOS_HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.DEPOS_HEADERS) - len(cur))
        new_nombre = nombre if nombre is not None else cur[0]
        new_id = cur[1]
        new_dir = direccion if direccion is not None else cur[2]
        new_desc = descripcion if descripcion is not None else cur[3]
        self._set(rng, [[new_nombre, new_id, new_dir, new_desc]])
        return True

    def delete_deposito_by_id(self, did: str) -> bool:
        self._ensure_tab_and_headers(self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB, self.DEPOS_HEADERS)
        tab = self.DELOS_TAB if hasattr(self, "DELOS_TAB") else self.DEPOS_TAB
        row = self._find_row_by_col_value(tab, 2, did)
        if not row:
            return False
        rng = f"{tab}!A{row}:{self._col_letter(len(self.DEPOS_HEADERS))}{row}"
        self._clear(rng)
        return True

    # ---------------------------------------------------------------------
    # USUARIOS
    # ---------------------------------------------------------------------
    def list_usuarios(self) -> List[Dict]:
        self._ensure_tab_and_headers(self.USERS_TAB, self.USERS_HEADERS)
        rng = f"{self.USERS_TAB}!A2:{self._col_letter(len(self.USERS_HEADERS))}"
        rows = self._get(rng)
        out = []
        for r in rows:
            nombre = (r[0].strip() if len(r) > 0 else "")
            correo = (r[1].strip() if len(r) > 1 else "")
            rango = (r[2].strip() if len(r) > 2 else "")
            if any([nombre, correo, rango]):
                out.append({"nombre": nombre, "correo": correo, "rango": rango})
        return out

    def add_usuario(self, nombre: str, correo: str, rango: str):
        self._ensure_tab_and_headers(self.USERS_TAB, self.USERS_HEADERS)
        self._append(f"{self.USERS_TAB}!A2", [[nombre, correo, rango]])

    def set_user_rango(self, correo: str, nuevo_rango: str) -> bool:
        self._ensure_tab_and_headers(self.USERS_TAB, self.USERS_HEADERS)
        row = self._find_row_by_col_value(self.USERS_TAB, 2, correo)  # col 2 = Correo
        if not row:
            return False
        rng = f"{self.USERS_TAB}!A{row}:{self._col_letter(len(self.USERS_HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.USERS_HEADERS) - len(cur))
        self._set(rng, [[cur[0], cur[1], nuevo_rango]])
        return True

    def delete_usuario_by_correo(self, correo: str) -> bool:
        self._ensure_tab_and_headers(self.USERS_TAB, self.USERS_HEADERS)
        row = self._find_row_by_col_value(self.USERS_TAB, 2, correo)
        if not row:
            return False
        rng = f"{self.USERS_TAB}!A{row}:{self._col_letter(len(self.USERS_HEADERS))}{row}"
        self._clear(rng)
        return True

    # ---------------------------------------------------------------------
    # LOG (solo lectura/escritura; sin edición)
    # ---------------------------------------------------------------------
    def list_log(self, limit: Optional[int] = 200) -> List[Dict]:
        self._ensure_tab_and_headers(self.LOG_TAB, self.LOG_HEADERS)
        rng = f"{self.LOG_TAB}!A2:{self._col_letter(len(self.LOG_HEADERS))}"
        rows = self._get(rng)
        out = []
        for r in rows:
            fecha = (r[0].strip() if len(r) > 0 else "")
            usuario = (r[1].strip() if len(r) > 1 else "")
            accion = (r[2].strip() if len(r) > 2 else "")
            if any([fecha, usuario, accion]):
                out.append({"fecha": fecha, "usuario": usuario, "accion": accion})
        if limit:
            out = out[-limit:]
        return out

    def write_log(self, usuario: str, accion: str, fecha_iso: Optional[str] = None):
        self._ensure_tab_and_headers(self.LOG_TAB, self.LOG_HEADERS)
        fecha = fecha_iso or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._append(f"{self.LOG_TAB}!A2", [[fecha, usuario, accion]])
