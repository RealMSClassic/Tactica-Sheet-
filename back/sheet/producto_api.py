# back/sheet/producto_api.py
from __future__ import annotations
from typing import List, Dict, Optional
from uuid import uuid4

from .base import SheetsBase


class ProductoAPI(SheetsBase):
    """
    Hoja: 'producto'
    Columnas base:
      data_ini_prox | RecID | codigo_producto | nombre_producto | descripcion_producto
    Columna de imagen (opcional): admite múltiples alias en la hoja:
      RecID_imagen | RecID_Imagen | RecId_imagen | RecId_Imagen | ID_imagen | ID_Imagen
    En la SALIDA de esta API, siempre normalizamos a la clave: "RecID_imagen".
    """

    TAB = "producto"

    HEADERS_BASE = [
        "data_ini_prox",
        "RecID",
        "codigo_producto",
        "nombre_producto",
        "descripcion_producto",
    ]

    # Cuando bootstrappeamos una hoja nueva, creamos esta columna:
    DEFAULT_IMG_HEADER = "RecID_imagen"

    # Alias aceptados para detectar la columna de imagen ya existente en la hoja:
    IMG_ALIASES = [
        "RecID_imagen",
        "RecID_Imagen",
        "RecId_imagen",
        "RecId_Imagen",
        "ID_imagen",
        "ID_Imagen",
    ]

    def __init__(self, page, sheet_id: Optional[str] = None):
        super().__init__(page, sheet_id)
        self._img_hdr: Optional[str] = None  # nombre EXACTO detectado en la hoja

    # ---------- internos: headers / detección de imagen ----------

    def _detect_img_header(self, hdrs: List[str]) -> Optional[str]:
        """Devuelve el nombre EXACTO de la cabecera de imagen si existe, según alias."""
        hs = set(hdrs or [])
        for alias in self.IMG_ALIASES:
            if alias in hs:
                return alias
        return None

    def _read_or_bootstrap_headers(self) -> List[str]:
        """
        Lee headers reales de la hoja. Si no existe, la crea con BASE + DEFAULT_IMG_HEADER.
        Guarda en self._img_hdr el nombre exacto de la columna de imagen si está.
        """
        try:
            hdrs = self._read_headers(self.TAB) or []
        except Exception:
            hdrs = []

        if hdrs:
            # Ya existe la hoja: detectamos nombre exacto de la columna de imagen (si hay)
            self._img_hdr = self._detect_img_header(hdrs)
            # Aseguramos que la hoja tenga los headers actuales tal como están
            self._ensure_tab_and_headers(self.TAB, hdrs)
            return hdrs

        # No hay headers: bootstrap con base + columna imagen por defecto
        hdrs = self.HEADERS_BASE + [self.DEFAULT_IMG_HEADER]
        self._img_hdr = self.DEFAULT_IMG_HEADER
        self._ensure_tab_and_headers(self.TAB, hdrs)
        return hdrs

    def _col_index(self, headers: List[str], name: str) -> Optional[int]:
        try:
            return headers.index(name)
        except ValueError:
            return None

    # ---------- API pública ----------

    def list(self) -> List[Dict]:
        """
        Lee todas las filas y devuelve dicts con claves normalizadas:
          RecID, codigo_producto, nombre_producto, descripcion_producto, (opcional) RecID_imagen
        """
        headers = self._read_or_bootstrap_headers()
        # Rango hasta la última columna realmente presente en la hoja
        rng = f"{self.TAB}!A2:{self._col_letter(len(headers))}"
        rows = self._get(rng) or []

        out: List[Dict] = []
        for r in rows:
            # Normalizar tamaño de fila a la cantidad de headers
            r = (r + [""] * len(headers))[:len(headers)]
            rec = dict(zip(headers, r))

            # Filtro: consideramos fila válida si hay algún dato clave
            if not any((
                rec.get("RecID"),
                rec.get("codigo_producto"),
                rec.get("nombre_producto"),
                rec.get("descripcion_producto"),
            )):
                continue

            item = {
                "RecID": (rec.get("RecID") or "").strip(),
                "codigo_producto": (rec.get("codigo_producto") or "").strip(),
                "nombre_producto": (rec.get("nombre_producto") or "").strip(),
                "descripcion_producto": (rec.get("descripcion_producto") or "").strip(),
            }

            # Si la hoja TIENE columna de imagen (cualquiera sea su alias), normalizamos a RecID_imagen
            if self._img_hdr and self._img_hdr in rec:
                item["RecID_imagen"] = (rec.get(self._img_hdr) or "").strip()

            out.append(item)

        return out

    def add(
        self,
        *,
        codigo_producto: str,
        nombre_producto: str,
        descripcion_producto: str = "",
        RecID_imagen: Optional[str] = None,
    ) -> str:
        """
        Inserta una nueva fila. Si la hoja tiene columna de imagen (con cualquier alias) la completa;
        si no, ignora el parámetro RecID_imagen.
        """
        headers = self._read_or_bootstrap_headers()

        recid = uuid4().hex[:10]
        # Construimos una fila vacía del largo correcto
        row = [""] * len(headers)

        # Seteamos por nombre de columna (robusto al orden real de la hoja)
        def set_if(col: str, value: str):
            idx = self._col_index(headers, col)
            if idx is not None:
                row[idx] = value

        set_if("data_ini_prox", "")
        set_if("RecID", recid)
        set_if("codigo_producto", (codigo_producto or "").strip())
        set_if("nombre_producto", (nombre_producto or "").strip())
        set_if("descripcion_producto", (descripcion_producto or "").strip())

        # Columna de imagen real (si existe en la hoja)
        if self._img_hdr and RecID_imagen is not None:
            set_if(self._img_hdr, (RecID_imagen or "").strip())

        self._append(f"{self.TAB}!A2", [row])
        return recid

    def update_by_recid(
        self,
        recid: str,
        *,
        codigo_producto: Optional[str] = None,
        nombre_producto: Optional[str] = None,
        descripcion_producto: Optional[str] = None,
        RecID_imagen: Optional[str] = None,
    ) -> bool:
        """
        Actualiza una fila existente por RecID. Si hay columna de imagen real en la hoja,
        y RecID_imagen no es None, la actualiza.
        """
        headers = self._read_or_bootstrap_headers()
        recid = (recid or "").strip()
        if not recid:
            return False

        # Índice de columna de RecID en los headers reales
        recid_col = self._col_index(headers, "RecID")
        if recid_col is None:
            return False

        # Buscar fila por RecID (columna B si el orden es estándar, pero mejor por índice detectado)
        row_idx = self._find_row_by_col_value(self.TAB, recid_col + 1, recid)  # +1 porque API usa 1-based
        if not row_idx:
            return False

        rng = f"{self.TAB}!A{row_idx}:{self._col_letter(len(headers))}{row_idx}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(headers) - len(cur))

        # Helper para asignar por nombre de columna real
        def set_if(col: str, value: Optional[str]):
            if value is None:
                return
            idx = self._col_index(headers, col)
            if idx is not None:
                cur[idx] = value

        # data_ini_prox vacío por convención
        set_if("data_ini_prox", "")

        set_if("codigo_producto", codigo_producto)
        set_if("nombre_producto", nombre_producto)
        set_if("descripcion_producto", descripcion_producto)

        # Imagen: usar el nombre EXACTO detectado en la hoja
        if self._img_hdr is not None and RecID_imagen is not None:
            set_if(self._img_hdr, RecID_imagen)

        self._set(rng, [cur])
        return True

    def delete_by_recid(self, recid: str) -> bool:
        headers = self._read_or_bootstrap_headers()
        recid = (recid or "").strip()
        if not recid:
            return False

        recid_col = self._col_index(headers, "RecID")
        if recid_col is None:
            return False

        row_idx = self._find_row_by_col_value(self.TAB, recid_col + 1, recid)
        if not row_idx:
            return False

        rng = f"{self.TAB}!A{row_idx}:{self._col_letter(len(headers))}{row_idx}"
        self._clear(rng)
        return True
