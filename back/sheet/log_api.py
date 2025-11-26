# back/sheet/log_api.py
from __future__ import annotations

import base64, json
from datetime import datetime
from typing import Optional

import flet as ft
from back.drive.drive_check import build_sheets_service

LOG_SHEET = "logs"  # columnas: data_ini_prox | fecha | ID_usuario | Accion


# ------------------ identidad (idéntica a la que venís usando) ------------------
def _jwt_payload(tok: str) -> dict:
    try:
        p = tok.split(".")
        if len(p) < 2:
            return {}
        b = p[1] + "=" * (-len(p[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(b.encode()))
    except Exception:
        return {}

def _get_identity(page: ft.Page) -> tuple[str, str]:
    """
    Devuelve (display_name, uid-like) para componer el log.
    Usamos el mismo enfoque que tu get_identity_from_token: prioriza name/email.
    """
    name = (
        page.session.get("user_name")
        or page.client_storage.get("user_name")
        or ""
    )
    email = (
        page.session.get("user_email")
        or page.client_storage.get("user_email")
        or ""
    )
    uid = (
        page.session.get("user_uid")
        or page.client_storage.get("user_uid")
        or ""
    )

    if not (name and (email or uid)):
        t = getattr(page.auth, "token", None)
        raw_id = getattr(t, "id_token", None) if t is not None else None
        if isinstance(raw_id, str):
            claims = _jwt_payload(raw_id)
            name = name or claims.get("name") or claims.get("given_name") or claims.get("preferred_username") or ""
            email = email or claims.get("email") or claims.get("upn") or claims.get("preferred_username") or ""
            uid = uid or claims.get("sub") or claims.get("oid") or claims.get("id") or ""

    if not (name and (email or uid)):
        u = getattr(page.auth, "user", None)
        name = name or getattr(u, "name", None) or (email or "")
        email = email or getattr(u, "email", None) or ""
        uid = uid or getattr(u, "id", None) or ""

    display_name = name or email or uid or "Invitado"
    return display_name, (uid or email or "1")


# ------------------ API de Log ------------------
class LogAPI:
    """
    Escribe filas en la hoja 'logs' con el formato:
    [ "", fecha, ID_usuario, Accion ]
    - ID_usuario: **nombre del usuario** (display_name), como pediste.
    - Auto-crea la pestaña 'logs' y siembra encabezados si faltan.
    """

    _ensured = False

    def __init__(self, page: ft.Page, sheet_id: str):
        self.page = page
        self.sheet_id = sheet_id
        self.sheets = build_sheets_service(page)

    # Garantiza que exista la hoja y los encabezados
    def _ensure_logs_sheet(self):
        if self._ensured:
            return
        try:
            meta = self.sheets.spreadsheets().get(
                spreadsheetId=self.sheet_id,
                fields="sheets.properties.title",
            ).execute()
            titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
            if LOG_SHEET not in titles:
                # crear pestaña logs
                self.sheets.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": LOG_SHEET}}}]},
                ).execute()
                # encabezados
                headers = [["data_ini_prox", "fecha", "ID_usuario", "Accion"]]
                self.sheets.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=f"{LOG_SHEET}!A1:D1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()
            else:
                # asegurar encabezados si están vacíos
                resp = self.sheets.spreadsheets().values().get(
                    spreadsheetId=self.sheet_id,
                    range=f"{LOG_SHEET}!A1:D1",
                ).execute()
                vals = resp.get("values", []) or []
                if not vals or len(vals[0]) < 4:
                    headers = [["data_ini_prox", "fecha", "ID_usuario", "Accion"]]
                    self.sheets.spreadsheets().values().update(
                        spreadsheetId=self.sheet_id,
                        range=f"{LOG_SHEET}!A1:D1",
                        valueInputOption="RAW",
                        body={"values": headers},
                    ).execute()
            self._ensured = True
        except Exception as e:
            # No levantamos excepción para no romper el flujo visual, pero lo dejamos en consola
            print("[WARN][logs] No se pudo asegurar la hoja 'logs':", e)

    def append(
        self,
        accion: str,
        *,
        id_usuario: Optional[str] = None,
        fecha: Optional[str] = None,
        include_user_name_in_action: bool = True,
    ) -> bool:
        """
        Inserta una fila en logs SOLO cuando la acción fue confirmada y OK (llamalo después del ok).
        - accion: texto de la acción, personalizado por el módulo.
        - id_usuario: si querés forzar; si no, guardamos el **nombre** del usuario actual.
        - fecha: si no se pasa, se usa ahora.
        """
        self._ensure_logs_sheet()

        display_name, _uid = _get_identity(self.page)
        ts = fecha or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action_text = f"{display_name} — {accion}" if include_user_name_in_action else accion

        # 👇 Guardamos el **NOMBRE** en ID_usuario
        row = ["", ts, (id_usuario or display_name), action_text]
        try:
            self.sheets.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=f"{LOG_SHEET}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
            return True
        except Exception as e:
            print("[WARN][logs] No se pudo insertar la fila de log:", e)
            return False


# ------------------ formateadores opcionales ------------------
def fmt_stock_add(cantidad: int | str, producto: str, deposito: str) -> str:
    return f"Agregó {cantidad} de '{producto}' al depósito '{deposito}'."

def fmt_stock_out(cantidad: int | str, producto: str, deposito: str) -> str:
    return f"Descargó {cantidad} de '{producto}' del depósito '{deposito}'."

def fmt_stock_move(cantidad: int | str, producto: str, dep_origen: str, dep_destino: str) -> str:
    return f"Movió {cantidad} de '{producto}' del depósito '{dep_origen}' al depósito '{dep_destino}'."

def fmt_user_invited(nombre: str, correo: str, rango: str) -> str:
    return f"Invitó al usuario '{nombre}' <{correo}> con rango '{rango}'."

def fmt_user_role_change(nombre: str, correo: str, old: str, new: str) -> str:
    return f"Cambió el rango de '{nombre}' <{correo}> de '{old}' a '{new}'."

def fmt_deposit_add(nombre: str) -> str:
    return f"Agrego deposito {nombre}"

def fmt_deposit_edit(old_id: str, new_id: str, old_name: str, new_name: str) -> str:
    return f"Edito\n  ID deposito  de {old_id} a {new_id}\n  Nombre  de {old_name} a {new_name}"

def fmt_deposit_delete(nombre: str, motivo: str) -> str:
    return f"Elimino el deposito {nombre} por el motivo de {motivo}"
