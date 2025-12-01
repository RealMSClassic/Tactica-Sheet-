# back/api_auth.py
print(">>> API_AUTH VERSION: CLEAN-PROD <<<")

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
    ):
        self.page = page
        self.user = None
        self.token = None
        self.on_success = on_success
        self.on_error = on_error

        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise RuntimeError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET faltan.")

        # 1) GOOGLE_REDIRECT_URI tiene prioridad total
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

        # 2) Si no existe, usar APP_ORIGIN
        if not redirect_uri:
            app_origin = os.getenv("APP_ORIGIN", "").strip().rstrip("/")
            if not app_origin:
                # solo en local
                app_origin = "http://127.0.0.1:8560"

            redirect_uri = f"{app_origin}/oauth_callback"

        print("[OAUTH] REDIRECT:", redirect_uri)

        self.provider = GoogleOAuthProvider(
            client_id=client_id,
            client_secret=client_secret,
            redirect_url=redirect_uri,
        )

        self.page.on_login = self._on_login

        if auto_load_existing:
            self._load_existing_auth()

    def _load_existing_auth(self):
        user = getattr(self.page.auth, "user", None)
        token = getattr(self.page.auth, "token", None)
        if user and token:
            exp = getattr(token, "expires_at", None)
            if exp and time.time() >= float(exp):
                self.logout()
                return
            self.user = user
            self.token = token

    def is_logged_in(self):
        return bool(self.user and self.token)

    def logout(self):
        try:
            self.page.logout()
        except:
            pass
        self.user = None
        self.token = None

    def login(self):
        try:
            self.provider.authorization_endpoint_params = {"prompt": "consent select_account"}
        except:
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
                self.on_error(e)
            return

        self.user = getattr(self.page.auth, "user", None)
        self.token = getattr(self.page.auth, "token", None)

        self.page.session.set("auth_in_progress", False)

        if self.on_success:
            self.on_success(self)
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
                print("decode error:", e)
        return {}

    def get_token(self):
<<<<<<< HEAD
        return getattr(self.token, "access_token", "") if self.token else ""
=======
        return getattr(self.token, "access_token", "") if self.token else ""
>>>>>>> 19155492efc18635caefb644b7d75f4e826609e5
