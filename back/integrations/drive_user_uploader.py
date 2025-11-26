# back/integrations/drive_user_uploader.py
from __future__ import annotations
import os, mimetypes
from typing import Optional, Dict, Any, Tuple
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]

def _guess_mime(path: str) -> str:
    mt, _ = mimetypes.guess_type(path)
    return mt or "application/octet-stream"

def _token_from_page(page) -> Optional[Dict[str, Any]]:
    """
    Intenta armar un token_dict a partir de:
      - page.auth.token (si existe)
      - page.client_storage["google_oauth_token"] / ["google_creds"] / ["google_token"]
    Completa client_id/secret desde env si hace falta.
    """
    def _with_client_info(tk: Dict[str, Any]) -> Dict[str, Any]:
        tk = dict(tk or {})
        tk.setdefault("token_uri", "https://oauth2.googleapis.com/token")
        tk.setdefault("scopes", DEFAULT_SCOPES)
        # completar client_id/secret desde env (necesarios para refrescar token)
        cid = os.getenv("GOOGLE_CLIENT_ID", "")
        csec = os.getenv("GOOGLE_CLIENT_SECRET", "")
        # si vienen vacíos y el token ya tiene client info, respetarlo
        tk.setdefault("client_id", cid)
        tk.setdefault("client_secret", csec)
        return tk

    # 1) page.auth.token
    try:
        if getattr(page, "auth", None) and isinstance(getattr(page.auth, "token", None), dict):
            tok = _with_client_info(page.auth.token)
            if tok.get("access_token"):
                return tok
    except Exception:
        pass

    # 2) client_storage
    for key in ("google_oauth_token", "google_creds", "google_token"):
        try:
            tok = page.client_storage.get(key)
            if isinstance(tok, dict):
                tok = _with_client_info(tok)
                if tok.get("access_token"):
                    return tok
        except Exception:
            pass

    return None


class DriveUserUploader:
    """
    Uploader de Drive con credenciales del USUARIO (OAuth).
    """

    def __init__(self, credentials: Credentials, *, use_shared_drives: bool = False):
        self.creds = credentials
        # cache_discovery=False evita warnings de pickling
        self.svc = build("drive", "v3", credentials=self.creds, cache_discovery=False)
        self.use_shared_drives = use_shared_drives

    # ---------- construcción desde la sesión Flet ----------
    @classmethod
    def from_page(cls, page, *, use_shared_drives: bool = False) -> "DriveUserUploader":
        tk = _token_from_page(page)
        if not tk or not tk.get("access_token"):
            raise RuntimeError("from_page: page.auth.token vacío o inválido.")

        # Armar Credentials. refresh_token puede venir vacío (funciona mientras no expire).
        creds = Credentials(
            token=tk.get("access_token"),
            refresh_token=tk.get("refresh_token"),
            token_uri=tk.get("token_uri") or "https://oauth2.googleapis.com/token",
            client_id=tk.get("client_id") or os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=tk.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=tk.get("scopes") or DEFAULT_SCOPES,
        )
        return cls(credentials=creds, use_shared_drives=use_shared_drives)

    # ---------- carpetas ----------
    def _find_child_folder(self, parent_id: str, name: str):
        name_esc = name.replace("'", r"\'")
        q = (
            f"'{parent_id}' in parents and "
            f"name = '{name_esc}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        res = self.svc.files().list(
            q=q, fields="files(id,name)", pageSize=1,
            supportsAllDrives=self.use_shared_drives,
            includeItemsFromAllDrives=self.use_shared_drives,
        ).execute()
        files = res.get("files", [])
        return files[0] if files else None

    def _create_folder(self, parent_id: str, name: str):
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        f = self.svc.files().create(
            body=meta, fields="id,name", supportsAllDrives=self.use_shared_drives
        ).execute()
        return f

    def ensure_path(self, path: str, root_id: Optional[str] = None) -> str:
        # por defecto: Mi Unidad del usuario
        cur = root_id or os.getenv("GDRIVE_ROOT_FOLDER_ID") or "root"
        parts = [p for p in path.split("/") if p and p != "."]
        for part in parts:
            found = self._find_child_folder(cur, part)
            cur = found["id"] if found else self._create_folder(cur, part)["id"]
        return cur

    # ---------- subida ----------
    def upload_file_get_view_link(self, local_path: str, folder_id: str, *, make_public: bool = True) -> Tuple[str, str]:
        name = os.path.basename(local_path)
        media = MediaFileUpload(local_path, mimetype=_guess_mime(local_path), resumable=False)
        meta = {"name": name, "parents": [folder_id]}
        f = self.svc.files().create(
            body=meta, media_body=media,
            fields="id, webViewLink, webContentLink",
            supportsAllDrives=self.use_shared_drives,
        ).execute()
        file_id = f["id"]

        if make_public:
            try:
                self.svc.permissions().create(
                    fileId=file_id,
                    body={"type": "anyone", "role": "reader"},
                    supportsAllDrives=self.use_shared_drives,
                ).execute()
            except Exception:
                pass

        try:
            f = self.svc.files().get(
                fileId=file_id,
                fields="id, webViewLink, webContentLink",
                supportsAllDrives=self.use_shared_drives,
            ).execute()
        except Exception:
            pass

        link = f.get("webViewLink") or f.get("webContentLink") or f"https://drive.google.com/file/d/{file_id}/view"
        return file_id, link

    def upload_to_path(self, local_path: str, path: str, *, root_id: Optional[str] = None, make_public: bool = True) -> Tuple[str, str]:
        folder_id = self.ensure_path(path, root_id=root_id)
        return self.upload_file_get_view_link(local_path, folder_id, make_public=make_public)

    def delete_file(self, file_id: str) -> None:
        self.svc.files().delete(fileId=file_id, supportsAllDrives=self.use_shared_drives).execute()
