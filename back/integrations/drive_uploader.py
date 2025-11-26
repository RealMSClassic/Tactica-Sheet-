# back/integrations/drive_uploader.py
from __future__ import annotations
import os
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# TODO: implementá tu flujo de credenciales aquí:
# - Si usás Service Account: from google.oauth2 import service_account
# - Si usás OAuth local: from google_auth_oauthlib.flow import InstalledAppFlow
# Dejé un stub para que inyectes credenciales.

SCOPES = ["https://www.googleapis.com/auth/drive"]

def _get_credentials():
    """
    TODO: reemplazar por tus credenciales.
    Ejemplo SA:
    creds = service_account.Credentials.from_service_account_file(
        'service_account.json', scopes=SCOPES
    )
    return creds
    """
    raise RuntimeError("DriveUploader: credenciales no configuradas. Implementá _get_credentials().")


class DriveUploader:
    def __init__(self, service=None):
        if service:
            self.service = service
        else:
            creds = _get_credentials()
            self.service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def _find_child_by_name(self, parent_id: str, name: str) -> Optional[str]:
        q = f"'{parent_id}' in parents and name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res = self.service.files().list(q=q, fields="files(id,name)").execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def _create_folder(self, parent_id: str, name: str) -> str:
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id] if parent_id else []
        }
        folder = self.service.files().create(body=file_metadata, fields="id").execute()
        return folder["id"]

    def _get_root_id(self) -> str:
        about = self.service.about().get(fields="rootFolderId").execute()
        return about["rootFolderId"]

    def ensure_path(self, path: str) -> str:
        """
        Crea (si no existe) y retorna el folderId para una ruta tipo "A/B/C".
        """
        parts = [p for p in path.strip("/").split("/") if p]
        parent = self._get_root_id()
        for name in parts:
            child = self._find_child_by_name(parent, name)
            if not child:
                child = self._create_folder(parent, name)
            parent = child
        return parent

    def upload_file_get_view_link(self, local_path: str, folder_id: str) -> tuple[str, str]:
        """
        Sube local_path al folder_id y retorna (file_id, view_link)
        """
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        filename = os.path.basename(local_path)
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaFileUpload(local_path, resumable=True)

        file = self.service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()
        fid = file["id"]

        # Compartir (anyone with link - reader)
        try:
            self.service.permissions().create(
                fileId=fid,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except HttpError:
            # Si falla, seguimos; quizá el dominio ya tiene permiso por defecto
            pass

        view_link = f"https://drive.google.com/file/d/{fid}/view"
        return fid, view_link
