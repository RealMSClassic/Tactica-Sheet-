# front/ventana_login.py
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

def login_view(page: ft.Page) -> ft.View:
    page.title = "Login - Táctica Sheet"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.scroll = "adaptive"

    # Helpers
    def cs_set(key: str, value):
        try:
            page.client_storage.set(key, value)
        except Exception:
            page.session.set(key, value)

    def now_s() -> float:
        return time.time()

    # ---------------------------
    # OAuth OK
    # ---------------------------
    def on_login_ok(handler: GoogleAuthHandler):
        cs_set("auth_in_progress", "0")
        cs_set("auth_started_at", "")

        tok_obj = getattr(handler, "token", None)

        access_token = getattr(tok_obj, "access_token", None)
        refresh_token = getattr(tok_obj, "refresh_token", None)
        id_token = getattr(tok_obj, "id_token", None)
        expires_in = getattr(tok_obj, "expires_in", None)
        token_type = getattr(tok_obj, "token_type", None)

        page.session.set("id_token", id_token)
        page.session.set("access_token", access_token)

        token_dict = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "id_token": id_token,
            "expires_in": expires_in,
            "token_type": token_type,
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "scopes": SCOPES,
        }

        cs_set("google_oauth_token", token_dict)
        page.go("/sheets")

    # ---------------------------
    # OAuth ERROR
    # ---------------------------
    def on_login_error(e):
        cs_set("auth_in_progress", "0")
        cs_set("auth_started_at", "")
        page.snack_bar = ft.SnackBar(ft.Text(f"Error de login: {getattr(e, 'error', e)}"))
        page.snack_bar.open = True
        page.update()
        page.go("/")

    # ---------------------------
    # Cuando el usuario hace click en “Ingresar con Google”
    # ---------------------------
    def on_click_login(_: ft.ControlEvent):
        cs_set("auth_in_progress", "1")
        cs_set("auth_started_at", str(now_s()))

        auth = GoogleAuthHandler(
            page,
            on_success=on_login_ok,
            on_error=on_login_error,
            skip_ngrok_warning=False,   # Producción limpia
        )

        auth.login()
        page.go("/loading")

    # UI
    logo = ft.Image(src="logo.png", width=180, height=180, fit=ft.ImageFit.CONTAIN)
    title = ft.Text("TACTICA Sheet", size=36, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87)
    subtitle = ft.Text("Gestor de Stocks", size=14, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_GREY_600)

    btn_login = ft.FilledButton(
        "Ingresar con Google",
        width=230, height=52,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.RED, color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12), elevation=3,
        ),
        on_click=on_click_login,
    )

    ui = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            colors=["#FFFFFF", "#FF5963", "#EE8B60"],
            stops=[0.0, 0.5, 1.0],
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
        ),
        content=ft.Container(
            gradient=ft.LinearGradient(
                colors=["#00FFFFFF", "#FFFFFF"],
                stops=[0.1, 0.3],
                begin=ft.alignment.top_center,
                end=ft.alignment.bottom_center,
            ),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                controls=[
                    ft.Container(
                        padding=ft.padding.only(top=60),
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                logo,
                                ft.Container(height=10),
                                title,
                                ft.Container(height=8),
                                subtitle,
                                ft.Container(height=8),
                            ],
                        ),
                    ),
                    ft.Container(
                        padding=ft.padding.only(left=16, right=16, bottom=84),
                        content=ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[btn_login]),
                    ),
                ],
            ),
        ),
    )

    return ft.View(route="/", controls=[ui])
