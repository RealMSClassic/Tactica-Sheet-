# back/sheets_ops.py
from __future__ import annotations

import requests
from datetime import datetime
import secrets
import uuid
from typing import Optional
import json, base64

import flet as ft

from back.drive.drive_check import (
    build_drive_service,
    build_sheets_service,
)

# =========================
#  Estructura por defecto
# =========================
DEFAULT_SHEET_DATA: dict[str, list[str]] = {
    "stock":         ["data_ini_prox", "RecID", "ID_producto", "ID_deposito", "cantidad"],
    "producto":      ["data_ini_prox", "RecID", "codigo_producto", "nombre_producto", "descripcion_producto", "RecID_Imagen"],
    "deposito":      ["data_ini_prox", "RecID", "ID_deposito", "nombre_deposito", "direccion_deposito", "descripcion_deposito", "RecID_Imagen"],
    "logs":          ["data_ini_prox", "fecha", "ID_usuario", "Accion"],
    "usuarios":      ["data_ini_prox", "RecID", "ID_usuario", "nombre_usuario", "correo_usuario", "rango_usuario", "RecID_Imagen"],
    "logsAcn":       ["data_ini_prox", "RecID", "tipo_accion", "movimiento"],
    "dataIndexInfo": ["data_ini_prox", "fecha_creacion", "version_sheet", "version_gestor"],
    # ✅ Nueva hoja
    "imagen":        ["data_ini_prox", "RecID", "ID_nombre"],
}

# =========================
#  Utilidades
# =========================
def _gen_recid() -> str:
    # ID url-safe legible; si preferís hex: return uuid.uuid4().hex
    return secrets.token_urlsafe(12)

def _col_letter(n: int) -> str:
    """Convierte 1->A, 2->B, ..., 27->AA, etc."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _jwt_payload(tok: str) -> dict:
    """Decodifica (sin verificar) el payload de un JWT para leer claims."""
    try:
        parts = tok.split(".")
        if len(parts) < 2:
            return {}
        b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(b64.encode()))
    except Exception:
        return {}

def _userinfo_from_google(access_token: str) -> dict:
    """Lee /userinfo de Google usando el access token (requiere scopes email y profile)."""
    try:
        url = "https://openidconnect.googleapis.com/v1/userinfo"
        r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        if r.status_code == 200:
            return r.json() or {}
    except Exception:
        pass
    return {}

def _get_identity_for_sheet_ops(page: ft.Page):
    """
    Devuelve (name, email, uid) usando, en este orden:
    - Valores en session/client_storage si ya están guardados
    - Claims del id_token (si lo hay)
    - /userinfo con el access_token como fallback (si faltan name/email)
    - page.auth.user como último recurso
    """
    # 1) Sesión / client_storage
    name  = page.session.get("user_name")  or page.client_storage.get("user_name")  or ""
    email = page.session.get("user_email") or page.client_storage.get("user_email") or ""
    uid   = page.session.get("user_uid")   or page.client_storage.get("user_uid")   or ""

    t = getattr(page.auth, "token", None)
    claims: dict = {}

    # 2) id_token claims
    if not (name and email and uid) and t is not None:
        raw_id = getattr(t, "id_token", None)
        if isinstance(raw_id, str):
            claims = _jwt_payload(raw_id) or {}
            name  = name  or claims.get("name") or claims.get("given_name") or claims.get("preferred_username") or ""
            email = email or claims.get("email") or claims.get("upn")        or claims.get("preferred_username") or ""
            uid   = uid   or claims.get("sub")   or claims.get("oid")        or claims.get("id")                 or ""

    # 3) /userinfo si falta name o email
    if (not name or not email) and t is not None:
        at = getattr(t, "access_token", None)
        if isinstance(at, str) and at:
            ui = _userinfo_from_google(at)
            if ui:
                name  = name  or ui.get("name") or ui.get("given_name") or ""
                email = email or ui.get("email") or ""
                uid   = uid   or ui.get("sub") or uid or ""

    # 4) page.auth.user como último recurso
    if not (name and email and uid):
        u = getattr(page.auth, "user", None)
        name  = name  or getattr(u, "name", None)  or ""
        email = email or getattr(u, "email", None) or ""
        uid   = uid   or getattr(u, "id", None)    or ""

    return name, email, uid

def _seed_after_create(page: ft.Page, sheets_service, spreadsheet_id: str, structure: dict[str, list[str]]):
    """
    Escribe:
    - dataIndexInfo!A2:D2  -> ["", fecha_creacion, "0.0.1", "0.2.0"]  (si existe esa hoja)
    - usuarios!A2:F2       -> ["", RecID, UID, display_name, email, "Administrador"] (si existe esa hoja)
      * display_name = name or email or uid
    """
    # 1) dataIndexInfo
    if "dataIndexInfo" in structure:
        headers = structure["dataIndexInfo"]
        last_col = _col_letter(len(headers))  # D
        fecha_creacion = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        values = [["", fecha_creacion, "0.0.1", "0.2.0"]]
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"dataIndexInfo!A2:{last_col}2",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

    # 2) usuarios
    if "usuarios" in structure:
        headers = structure["usuarios"]
        last_col = _col_letter(len(headers))  # F
        name, email, uid = _get_identity_for_sheet_ops(page)
        display_name = name or email or uid or "Invitado"
        recid = uuid.uuid4().hex

        # ID_usuario = UID del token (fallback "1" si no hay uid por alguna razón)
        id_usuario = uid or "1"

        values = [["", recid, id_usuario, display_name, email or "", "Administrador"]]
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"usuarios!A2:{last_col}2",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

# =========================
#  Creación del Spreadsheet
# =========================
def create_spreadsheet_with_structure(
    page: ft.Page,
    folder_id: str,
    spreadsheet_name: str,
    sheet_data: dict[str, list[str]] | None = None,
) -> str:
    """
    Crea un Spreadsheet en Drive (dentro de folder_id) con tabs y encabezados.
    Elimina la hoja por defecto y agrega las definidas en sheet_data.
    Luego siembra dataIndexInfo y usuarios.
    Devuelve el spreadsheet_id.
    """
    structure = sheet_data or DEFAULT_SHEET_DATA

    # Crear archivo vacío (tipo Google Spreadsheet) en la carpeta destino
    drive = build_drive_service(page)
    file = drive.files().create(
        body={
            "name": spreadsheet_name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [folder_id],
        },
        fields="id",
        supportsAllDrives=True,
    ).execute()
    spreadsheet_id = file["id"]

    sheets = build_sheets_service(page)

    # Hoja por defecto (Sheet1) -> la eliminamos luego
    meta = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    default_sheet_id = meta["sheets"][0]["properties"]["sheetId"]

    # 1) Agregar todas las hojas que definimos
    requests = [{"addSheet": {"properties": {"title": name}}} for name in structure.keys()]
    # 2) Borrar la hoja por defecto
    requests.append({"deleteSheet": {"sheetId": default_sheet_id}})

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": requests}
    ).execute()

    # Escribir encabezados en cada hoja
    for tab_name, headers in structure.items():
        last_col = _col_letter(len(headers))
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{tab_name}!A1:{last_col}1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()

    # Seed de dataIndexInfo y usuarios
    try:
        _seed_after_create(page, sheets, spreadsheet_id, structure)
    except Exception as se:
        print("[WARN] No se pudo sembrar dataIndexInfo / usuarios:", se)

    return spreadsheet_id

# =========================
#  INDEX (alta/baja/cambio)
# =========================
def append_index_row(
    page: ft.Page,
    index_sheet_id: str,
    nombre_sheet: str,
    new_sheet_id: str,
    correo_origen: str,
    estado_user: str = "Administrador",
) -> None:
    """
    Agrega una fila al indexSheetList con:
    ["" (columna data_ini_prox), RecID, nombre_sheet, id_sheet, correo_origen, estado_user, fecha_creacion]
    """
    sheets = build_sheets_service(page)
    recid = _gen_recid()
    fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    row = ["", recid, nombre_sheet, new_sheet_id, correo_origen, estado_user, fecha_str]

    sheets.spreadsheets().values().append(
        spreadsheetId=index_sheet_id,
        range="A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

def _find_index_row_by_sheet_id(page: ft.Page, index_sheet_id: str, sheet_id: str) -> Optional[int]:
    """
    Busca en D2:D la primera coincidencia con sheet_id.
    Devuelve el número de fila (1-based) o None.
    """
    sheets = build_sheets_service(page)
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=index_sheet_id,
        range="D2:D",
    ).execute()
    vals = resp.get("values", []) or []
    for i, row in enumerate(vals, start=2):  # fila real = i (comienza en 2)
        v = (row[0].strip() if row else "")
        if v == sheet_id:
            return i
    return None

def update_index_name_by_sheet_id(page: ft.Page, index_sheet_id: str, sheet_id: str, new_name: str) -> bool:
    row = _find_index_row_by_sheet_id(page, index_sheet_id, sheet_id)
    if not row:
        return False
    sheets = build_sheets_service(page)
    sheets.spreadsheets().values().update(
        spreadsheetId=index_sheet_id,
        range=f"C{row}:C{row}",
        valueInputOption="RAW",
        body={"values": [[new_name]]},
    ).execute()
    return True

def clear_index_row_by_sheet_id(page: ft.Page, index_sheet_id: str, sheet_id: str) -> bool:
    row = _find_index_row_by_sheet_id(page, index_sheet_id, sheet_id)
    if not row:
        return False
    sheets = build_sheets_service(page)
    # Limpia A..G de esa fila; tu índice usa 7 columnas
    sheets.spreadsheets().values().clear(
        spreadsheetId=index_sheet_id,
        range=f"A{row}:G{row}",
        body={},
    ).execute()
    return True

# =========================
#  DRIVE ops
# =========================
def rename_file_in_drive(page: ft.Page, file_id: str, new_name: str) -> None:
    drive = build_drive_service(page)
    drive.files().update(
        fileId=file_id,
        body={"name": new_name},
        supportsAllDrives=True,
    ).execute()

def trash_file_in_drive(page: ft.Page, file_id: str) -> None:
    drive = build_drive_service(page)
    drive.files().update(
        fileId=file_id,
        body={"trashed": True},
        supportsAllDrives=True,
    ).execute()
