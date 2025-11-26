from googleapiclient.discovery import build
from google.auth.transport.requests import Request

class GestorBackend:
    def __init__(self, page, *args, **kwargs):
        self.page = page
        self._drive = None
        self._sheets = None

    def _get_creds(self):
        auth = getattr(self.page, "auth_handler", None)
        if not auth:
            raise RuntimeError("No hay auth_handler en page; ¿te logueaste?")
        creds = auth.get_google_credentials()
        if not creds:
            raise RuntimeError("No hay credenciales de Google.")
        # refresca si venció y tenés refresh_token
        if getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
            creds.refresh(Request())
        return creds

    def drive(self):
        if self._drive is None:
            creds = self._get_creds()
            # cache_discovery=False evita warnings
            self._drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._drive

    def sheets(self):
        if self._sheets is None:
            creds = self._get_creds()
            self._sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return self._sheets
