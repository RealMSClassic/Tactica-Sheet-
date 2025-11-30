# back/api_auth.py

print(">>>>>>>>>>> API_AUTH_VERSION: 5-FINAL-OK <<<<<<<<<<<")
import os
import time
import flet as ft
from dotenv import load_dotenv
from flet.auth.providers import GoogleOAuthProvider
from google.oauth2 import id_token
from google.auth.transport import requests as greq

class GoogleAuthHandler:
    def __init__(
        self,
        page: ft.Page,
        on_success=None,
        on_error=None,
        auto_load_existing: bool = True,
    ):
        self.page = page
        self.user = None
        self.token = None
        self.on_success = on_success
        self.on_error = on_error

        # Cargar .env solo en local
        load_dotenv()

        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise RuntimeError("GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET no están definidos.")

        # PRIORIDAD 1: redirect explícito (si existe)
        redirect_uri_env = os.getenv("GOOGLE_REDIRECT_URI")

        # PRIORIDAD 2: APP_ORIGIN
        app_origin_env = os.getenv("APP_ORIGIN", "").strip().rstrip("/")

        if redirect_uri_env:
            redirect_url = redirect_uri_env

        else:
            # si app_origin no está definido → local
            if app_origin_env:
                origin = app_origin_env
            else:
                origin = "http://127.0.0.1:8560"

            redirect_url = f"{origin}/oauth_callback"

        print("[OAUTH] CLIENT_ID:", client_id)
        print("[OAUTH] REDIRECT_URL:", redirect_url)

        self.provider = GoogleOAuthProvider(
            client_id=client_id,
            client_secret=client_secret,
            redirect_url=redirect_url,
        )

        self.page.on_login = self._on_login

        if auto_load_existing:
            self._load_existing_auth()

    def _load_existing_auth(self):
        existing_user = getattr(self.page.auth, "user", None)
        existing_token = getattr(self.page.auth, "token", None)
        if existing_user and existing_token:
            expires_at = getattr(existing_token, "expires_at", None)
            if expires_at and isinstance(expires_at, (int, float)) and time.time() >= float(expires_at):
                self.logout()
                return
            self.user = existing_user
            self.token = existing_token

    def is_logged_in(self) -> bool:
        return bool(self.user and self.token) or bool(getattr(self.page.auth, "token", None))

    def logout(self):
        try:
            self.page.logout()
        except Exception:
            pass
        self.user = None
        self.token = None

    def login(self, force_select_account: bool = True):
        try:
            self.provider.authorization_endpoint_params = {"prompt": "consent select_account"}
        except Exception:
            pass

        self.page.login(
            self.provider,
            scope=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/spreadsheets",
            ],
        )

    def _on_login(self, e: ft.LoginEvent):
        if e.error:
            if self.on_error:
                try:
                    self.on_error(e)
                except Exception:
                    pass
            return

        self.user = getattr(self.page.auth, "user", None)
        self.token = getattr(self.page.auth, "token", None)

        try:
            self.page.client_storage.set("auth_in_progress", "0")
            self.page.client_storage.set("auth_started_at", "")
        except Exception:
            pass

        self.page.session.set("auth_in_progress", False)

        if self.on_success:
            try:
                self.on_success(self)
            except Exception:
                pass
        else:
            self.page.go("/sheets")

        self.page.update()

    def get_user_info(self):
        if self.user:
            return {
                "id": getattr(self.user, "id", None) or getattr(self.user, "sub", None),
                "email": getattr(self.user, "email", None),
                "name": getattr(self.user, "name", None),
            }

        if self.token and getattr(self.token, "id_token", None):
            try:
                info = id_token.verify_oauth2_token(
                    self.token.id_token,
                    greq.Request(),
                    self.provider.client_id,
                )
                return {
                    "id": info.get("sub"),
                    "email": info.get("email"),
                    "name": info.get("name"),
                }
            except Exception as e:
                print("[USER INFO] Error al decodificar id_token:", e)
        else:
            print("[USER INFO] No hay user ni id_token disponible")

        return {}

    def get_token(self) -> str:
        return getattr(self.token, "access_token", "") if self.token else ""
