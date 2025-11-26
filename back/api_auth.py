# back/api_auth.py
import os
import time
import flet as ft
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
        origin: str | None = None,
        skip_ngrok_warning: bool = True,
    ):
        self.page = page
        self.user = None
        self.token = None
        self.on_success = on_success
        self.on_error = on_error

        client_id = os.getenv("GOOGLE_CLIENT_ID") or "249531315844-0fmb6ms8ql00a5nhqkbeasd32pdrktv7.apps.googleusercontent.com"
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or "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"

        origin = (origin or os.getenv("NGROK_ORIGIN") or "").strip().rstrip("/")
        is_mobile = (self.page.platform in ("android", "ios"))

        if not origin:
            if is_mobile:
                raise RuntimeError("NGROK_ORIGIN no definido para móvil.")
            origin = "http://127.0.0.1:8560"

        if is_mobile and ("localhost" in origin or "127.0.0.1" in origin):
            raise RuntimeError(f"Origen inválido en móvil: {origin}")

        redirect_url = f"{origin}/oauth_callback"
        if skip_ngrok_warning:
            redirect_url += "?ngrok-skip-browser-warning=1"

        print("[OAUTH] client_id:", client_id)
        print("[OAUTH] redirect_url:", redirect_url)

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
                self.logout(); return
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

    # back/api_auth.py
    def _on_login(self, e: ft.LoginEvent):
        if e.error:
            # ... tu manejo actual de error ...
            if self.on_error:
                try:
                    self.on_error(e)
                except Exception:
                    pass
            return

        # marcar sesión
        self.user = getattr(self.page.auth, "user", None)
        self.token = getattr(self.page.auth, "token", None)

        # ✅ SIEMPRE apagar el flag de carga (por si estás en /loading)
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
            # fallback: si no te pasaron callback, andá al selector
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
