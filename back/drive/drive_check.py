# back/drive/drive_check.py
from datetime import datetime
import flet as ft
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _creds_from_flet(
    page: ft.Page,
    extra_scopes=None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> Credentials:
    t = getattr(page.auth, "token", None)
    assert t and getattr(t, "access_token", None), "No hay token en page.auth; hacé login primero."

    scopes = set(DRIVE_SCOPES + SHEETS_SCOPES)
    if extra_scopes:
        scopes |= set(extra_scopes)

    creds = Credentials(
        token=t.access_token,
        refresh_token=getattr(t, "refresh_token", None),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes),
    )

    # expiry UTC naive (evita aware vs naive)
    expires_at = getattr(t, "expires_at", None)
    if expires_at:
        creds.expiry = datetime.utcfromtimestamp(float(expires_at))

    try:
        if creds.expired and creds.refresh_token and creds.client_id and creds.client_secret:
            creds.refresh(Request())
    except Exception:
        pass

    return creds


def build_drive_service(page: ft.Page, client_id: str | None = None, client_secret: str | None = None):
    creds = _creds_from_flet(page, client_id=client_id, client_secret=client_secret)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def build_sheets_service(page: ft.Page, client_id: str | None = None, client_secret: str | None = None):
    creds = _creds_from_flet(page, client_id=client_id, client_secret=client_secret)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


# -------------------- Folders & Files helpers --------------------

def find_folder_id(page: ft.Page, folder_name: str, parent_id: str | None = None) -> str | None:
    service = build_drive_service(page)
    safe_name = folder_name.replace("'", r"\'")
    q = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        q += f" and '{parent_id}' in parents"

    resp = service.files().list(
        q=q, spaces="drive",
        fields="files(id,name,parents)",
        pageSize=100,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def create_folder(page: ft.Page, folder_name: str, parent_id: str | None = None) -> str:
    service = build_drive_service(page)
    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    file = service.files().create(
        body=metadata, fields="id", supportsAllDrives=True
    ).execute()
    return file["id"]


def get_or_create_folder_id(page: ft.Page, folder_name: str, parent_id: str | None = None) -> str:
    fid = find_folder_id(page, folder_name, parent_id=parent_id)
    return fid if fid else create_folder(page, folder_name, parent_id=parent_id)


# -------------------- Public sharing helpers --------------------

def has_anyone_reader(page: ft.Page, file_id: str) -> bool:
    """Devuelve True si el recurso ya tiene permiso 'anyone'."""
    service = build_drive_service(page)
    try:
        resp = service.permissions().list(
            fileId=file_id,
            fields="permissions(id,type,role,allowFileDiscovery)",
            supportsAllDrives=True,
        ).execute()
        perms = resp.get("permissions", [])
        for p in perms:
            if p.get("type") == "anyone" and p.get("role") in ("reader", "writer", "owner"):
                return True
        return False
    except Exception:
        return False


def ensure_anyone_with_link_reader(page: ft.Page, file_id: str) -> bool:
    """
    Garantiza que el recurso sea accesible como 'Cualquiera con el enlace (lector)'.
    Para carpetas, esto aplica a la carpeta y sus contenidos suelen heredar (según Drive).
    """
    if has_anyone_reader(page, file_id):
        return True

    service = build_drive_service(page)
    body = {
        "type": "anyone",
        "role": "reader",
        # False => “con el enlace”, no indexado por búsqueda
        "allowFileDiscovery": False,
    }
    try:
        service.permissions().create(
            fileId=file_id,
            body=body,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return True
    except HttpError as e:
        print("[Drive] No se pudo asignar permiso 'anyone' al recurso:", e)
        return False
    except Exception as e:
        print("[Drive] Error estableciendo permiso público:", e)
        return False


# -------------------- Imagen folder inside TacticaGestorSheet --------------------

def get_or_create_root_folder(page: ft.Page, root_name: str = "TacticaGestorSheet") -> str:
    """Devuelve el ID de la carpeta raíz del sistema; la crea si no existe."""
    return get_or_create_folder_id(page, root_name, parent_id=None)


def get_or_create_image_folder_id(
    page: ft.Page,
    parent_id: str,
    folder_name: str = "GestorImagen",
) -> str:
    """
    Crea (o recupera) la carpeta de imágenes 'GestorImagen' dentro de 'TacticaGestorSheet'
    y asegura el permiso “Cualquiera con el enlace (lector)”.
    """
    fid = find_folder_id(page, folder_name, parent_id=parent_id)
    if not fid:
        fid = create_folder(page, folder_name, parent_id=parent_id)
    # Asegurar acceso público por enlace
    ensure_anyone_with_link_reader(page, fid)
    return fid


def get_or_create_tactica_image_folder(page: ft.Page) -> dict:
    """
    Conveniencia: devuelve dict con IDs de raíz y de la carpeta de imágenes,
    creando lo que falte y dejando 'GestorImagen' pública (lector).
    """
    root_id = get_or_create_root_folder(page, root_name="TacticaGestorSheet")
    image_id = get_or_create_image_folder_id(page, parent_id=root_id, folder_name="GestorImagen")
    return {"root_id": root_id, "image_id": image_id}


# -------------------- Sheets helpers --------------------

def find_spreadsheet_in_folder(page: ft.Page, name: str, folder_id: str) -> str | None:
    service = build_drive_service(page)
    safe_name = name.replace("'", r"\'")
    q = (
        f"name = '{safe_name}' and "
        f"mimeType = 'application/vnd.google-apps.spreadsheet' and "
        f"trashed = false and '{folder_id}' in parents"
    )
    resp = service.files().list(
        q=q, spaces="drive",
        fields="files(id,name)",
        pageSize=50,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def create_spreadsheet_in_folder(page: ft.Page, name: str, folder_id: str) -> str:
    service = build_drive_service(page)
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [folder_id]}
    file = service.files().create(
        body=metadata, fields="id", supportsAllDrives=True
    ).execute()
    return file["id"]


def build_sheets_headers() -> list[str]:
    return [
        "data_ini_prox", "RecID", "nombre_sheet", "id_sheet",
        "correo_origen", "estado_user", "fecha_creacion",
    ]


def write_headers_if_empty(page: ft.Page, spreadsheet_id: str, headers: list[str] | None = None):
    if headers is None:
        headers = build_sheets_headers()
    sheets = build_sheets_service(page)
    # si A1 está vacío -> escribir headers
    res = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range="A1:A1"
    ).execute()
    has_value = bool(res.get("values"))
    if not has_value:
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def get_or_create_index_sheet(page: ft.Page, folder_id: str, index_name: str = "indexSheetList") -> str:
    """
    Si existe el spreadsheet `index_name` dentro de folder_id → devuelve su ID.
    Si no existe, lo crea y escribe los headers.
    """
    sid = find_spreadsheet_in_folder(page, index_name, folder_id)
    if not sid:
        sid = create_spreadsheet_in_folder(page, index_name, folder_id)
    write_headers_if_empty(page, sid, headers=build_sheets_headers())
    return sid


def list_spreadsheets_in_folder(page: ft.Page, folder_id: str, exclude_names: set[str] | None = None) -> list[dict]:
    service = build_drive_service(page)
    q = (
        f"mimeType = 'application/vnd.google-apps.spreadsheet' and "
        f"trashed = false and '{folder_id}' in parents"
    )
    results = []
    page_token = None
    while True:
        resp = service.files().list(
            q=q, spaces="drive",
            fields="nextPageToken, files(id,name)",
            pageSize=100, pageToken=page_token,
            includeItemsFromAllDrives=True, supportsAllDrives=True,
        ).execute()
        for f in resp.get("files", []):
            if not exclude_names or f["name"] not in exclude_names:
                results.append({"name": f["name"], "id": f["id"]})
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results
