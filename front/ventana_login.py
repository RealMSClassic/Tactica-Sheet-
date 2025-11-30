# front/ventana_login.py
print(">>> LOGIN_VIEW VERSION: CLEAN-PROD <<<")

import os
import time
import flet as ft
from back.api_auth import GoogleAuthHandler

AUTH_WINDOW_SEC = 120

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

def login_view(page: ft.Page):
    page.title = "Login - Táctica Sheet"
    page.bgcolor = ft.Colors.WHITE

    def cs_set(k, v):
        try: page.client_storage.set(k, v)
        except: page.session.set(k, v)

    def on_login_ok(handler):
        tok = handler.token

        token_dict = {
            "access_token": getattr(tok, "access_token", None),
            "refresh_token": getattr(tok, "refresh_token", None),
            "id_token": getattr(tok, "id_token", None),
            "expires_in": getattr(tok, "expires_in", None),
            "token_type": getattr(tok, "token_type", None),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "scopes": SCOPES,
        }

        cs_set("google_oauth_token", token_dict)
        page.go("/sheets")

    def on_login_error(e):
        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {e.error}"))
        page.snack_bar.open = True
        page.update()

    def on_click_login(_):
        cs_set("auth_in_progress", "1")
        auth = GoogleAuthHandler(
            page,
            on_success=on_login_ok,
            on_error=on_login_error,
        )
        auth.login()
        page.go("/loading")

    btn_login = ft.FilledButton(
        "Ingresar con Google",
        on_click=on_click_login,
    )

    return ft.View("/", [btn_login])
