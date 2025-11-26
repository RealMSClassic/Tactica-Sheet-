from __future__ import annotations
from typing import List, Dict, Optional
from uuid import uuid4

from .base import SheetsBase


class UsuarioAPI(SheetsBase):
    """
    Hoja: 'usuarios'
    Encabezados exactos (fila 1):
    data_ini_prox | RecID | ID_usuario | nombre_usuario | correo_usuario | rango_usuario
    """
    TAB = "usuarios"
    HEADERS = ["data_ini_prox", "RecID", "ID_usuario", "nombre_usuario", "correo_usuario", "rango_usuario"]

    # -------------------------- utils internos --------------------------

    def _ensure(self):
        """Asegura pestaña y headers (no siembra aquí)."""
        self._ensure_tab_and_headers(self.TAB, self.HEADERS)

    def _auth_user_info(self) -> Optional[Dict[str, str]]:

        try:
            a = getattr(self.page, "auth", None)
            if not a:
                return None

            u = getattr(a, "user", None) or a
            uid = getattr(u, "id", None) or getattr(u, "user_id", None) or getattr(u, "sub", None)
            name = getattr(u, "name", None) or getattr(u, "display_name", None) or getattr(u, "given_name", None)
            email = getattr(u, "email", None)

            claims = getattr(a, "claims", None)
            if claims and isinstance(claims, dict):
                uid = uid or claims.get("sub") or claims.get("id")
                name = name or claims.get("name") or (
                    f"{claims.get('given_name','')} {claims.get('family_name','')}".strip()
                )
                email = email or claims.get("email")

            if not email:
                return None

            return {"id": (uid or "").strip(), "name": (name or "").strip(), "email": (email or "").strip()}
        except Exception:
            return None

    # -------------------------- siembra en creación --------------------------

    def seed_admin_from_auth(self) -> Optional[str]:
        """
        Asegura la pestaña 'usuarios' y, si está VACÍA, inserta un usuario Administrador
        usando el dueño del token actual (page.auth). No duplica si ya hay filas.
        Devuelve el RecID creado o None si no sembró.
        """
        self._ensure()

        # ¿ya hay filas?
        colB = self._get(f"{self.TAB}!B2:B")
        has_any = any((r and (r[0] or "").strip()) for r in colB)
        if has_any:
            return None

        info = self._auth_user_info()
        if not info:
            return None

        recid = uuid4().hex[:10]
        self._append(
            f"{self.TAB}!A2",
            [["", recid, info["id"], info["name"], info["email"], "Administrador"]],
        )
        return recid

    # -------------------------- CRUD --------------------------

    def list(self) -> List[Dict]:
        """Devuelve usuarios como dicts sin la col A (vacía)."""
        self._ensure()
        rng = f"{self.TAB}!A2:{self._col_letter(len(self.HEADERS))}"
        rows = self._get(rng)
        out: List[Dict] = []
        for r in rows:
            r = (r + [""] * len(self.HEADERS))[:len(self.HEADERS)]
            if any([r[1].strip(), r[2].strip(), r[3].strip(), r[4].strip(), r[5].strip()]):
                out.append({
                    "RecID": r[1].strip(),
                    "ID_usuario": r[2].strip(),
                    "nombre_usuario": r[3].strip(),
                    "correo_usuario": r[4].strip(),
                    "rango_usuario": r[5].strip(),
                })
        return out

    def _find_row_by_recid(self, recid: str) -> Optional[int]:
        """Fila (1-based) donde B == RecID."""
        recid = (recid or "").strip()
        if not recid:
            return None
        return self._find_row_by_col_value(self.TAB, 2, recid)

    def add(self, *, ID_usuario: str, nombre_usuario: str, correo_usuario: str, rango_usuario: str) -> str:
        """
        Inserta: ["", RecID_aleatorio, ID_usuario, nombre, correo, rango] y devuelve RecID.
        """
        self._ensure()
        ID_usuario = (ID_usuario or "").strip()
        nombre_usuario = (nombre_usuario or "").strip()
        correo_usuario = (correo_usuario or "").strip()
        rango_usuario = (rango_usuario or "").strip()

        if not nombre_usuario or not correo_usuario:
            raise ValueError("Completá nombre y correo.")
        if "@" not in correo_usuario or "." not in correo_usuario.split("@")[-1]:
            raise ValueError("Correo inválido.")
        # evitar duplicado por correo
        if self._find_row_by_col_value(self.TAB, 5, correo_usuario):
            raise ValueError("El correo ya existe.")

        recid = uuid4().hex[:10]
        self._append(
            f"{self.TAB}!A2",
            [["", recid, ID_usuario, nombre_usuario, correo_usuario, rango_usuario]],
        )
        return recid

    def update_by_recid(
        self,
        recid: str,
        *,
        nombre_usuario: Optional[str] = None,
        correo_usuario: Optional[str] = None,
        rango_usuario: Optional[str] = None,
        ID_usuario: Optional[str] = None,
    ) -> bool:
        """Actualiza campos indicados (None = no cambia)."""
        self._ensure()
        row = self._find_row_by_recid(recid)
        if not row:
            return False

        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        cur = (self._get(rng) or [[]])[0]
        cur += [""] * (len(self.HEADERS) - len(cur))

        new_idusr = cur[2] if ID_usuario is None else ID_usuario
        new_nombre = cur[3] if nombre_usuario is None else nombre_usuario
        new_correo = cur[4] if correo_usuario is None else correo_usuario
        new_rango = cur[5] if rango_usuario is None else rango_usuario

        if correo_usuario is not None:
            if "@" not in new_correo or "." not in new_correo.split("@")[-1]:
                return False

        self._set(rng, [["", cur[1], new_idusr, new_nombre, new_correo, new_rango]])
        return True

    def delete_by_recid(self, recid: str) -> bool:
        """Elimina por RecID (col B)."""
        self._ensure()
        row = self._find_row_by_recid(recid)
        if not row:
            return False
        rng = f"{self.TAB}!A{row}:{self._col_letter(len(self.HEADERS))}{row}"
        self._clear(rng)
        return True
