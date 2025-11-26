# front/ventana_login.py
import os
import time
import flet as ft
from back.api_auth import GoogleAuthHandler

AUTH_WINDOW_SEC = 120  # mantener igual que en loading/main

# Scopes que queremos conservar junto al token para Drive/Sheets
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

    # ---- helpers persistentes ----
    def cs_set(key: str, value):
        try:
            page.client_storage.set(key, value)
        except Exception:
            page.session.set(key, value)

    def now_s() -> float:
        return time.time()

    # ---- callbacks OAuth ----
    def on_login_ok(handler: GoogleAuthHandler):
        # apaga el “cargando”
        cs_set("auth_in_progress", "0")
        cs_set("auth_started_at", "")

        # Guarda “rápidos” (opcional)
        tok_obj = getattr(handler, "token", None)
        access_token = None
        refresh_token = None
        id_token = None
        expires_in = None
        token_type = None

        # handler.token puede ser dict o un objeto con attrs
        if isinstance(tok_obj, dict):
            access_token = tok_obj.get("access_token")
            refresh_token = tok_obj.get("refresh_token")
            id_token = tok_obj.get("id_token")
            expires_in = tok_obj.get("expires_in")
            token_type = tok_obj.get("token_type")
        else:
            access_token = getattr(tok_obj, "access_token", None)
            refresh_token = getattr(tok_obj, "refresh_token", None)
            id_token = getattr(tok_obj, "id_token", None)
            expires_in = getattr(tok_obj, "expires_in", None)
            token_type = getattr(tok_obj, "token_type", None)

        page.session.set("id_token", id_token)
        page.session.set("access_token", access_token)

        # ✅ GUARDAR TOKEN COMPLETO EN client_storage
        token_dict = {
            "access_token": access_token,
            "refresh_token": refresh_token,  # puede venir None si no pediste offline
            "id_token": id_token,
            "expires_in": expires_in,
            "token_type": token_type,
            "token_uri": "https://oauth2.googleapis.com/token",
            # completamos client_id / client_secret desde env (necesarios para refrescar token)
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "scopes": SCOPES,
        }
        # Esto es lo que tu DriveUserUploader.from_page espera encontrar.
        cs_set("google_oauth_token", token_dict)

        # navega al selector
        page.go("/sheets")

    def on_login_error(e):
        cs_set("auth_in_progress", "0")
        cs_set("auth_started_at", "")
        page.snack_bar = ft.SnackBar(ft.Text(f"Error de login: {getattr(e, 'error', e)}"))
        page.snack_bar.open = True
        page.update()
        page.go("/")  # volvemos a login

    # Si tenés un dominio público para OAuth
    CURRENT_ORIGIN = "https://shepherd-correct-intensely.ngrok-free.app"

    # ---- UI ----
    logo = ft.Image(src="logo.png", width=180, height=180, fit=ft.ImageFit.CONTAIN)
    title = ft.Text("TACTICA Sheet", size=36, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87)
    subtitle = ft.Text("Gestor de Stocks", size=14, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_GREY_600)

    def on_click_login(_: ft.ControlEvent):
        # marcar “en progreso” y mandar a /loading
        cs_set("auth_in_progress", "1")
        cs_set("auth_started_at", str(now_s()))

        # Crear el handler y disparar login (tu handler ya abre popup)
        auth = GoogleAuthHandler(
            page,
            on_success=on_login_ok,
            on_error=on_login_error,
            origin=CURRENT_ORIGIN,
            skip_ngrok_warning=True,
        )

        # Si tu GoogleAuthHandler permite configurar scopes / access_type / prompt,
        # asegurate de pasarlos ahí dentro (depende de tu implementación).
        # auth.login(scopes=SCOPES, access_type="offline", prompt="consent")
        auth.login()
        page.go("/loading")

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
