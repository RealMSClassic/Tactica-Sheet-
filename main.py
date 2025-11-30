# main.py
import os
import secrets
from pathlib import Path
import flet as ft
from dotenv import load_dotenv
from front.ventana_login import login_view  # solo login arriba; el resto, lazy import

# Cargar variables de entorno desde .env
load_dotenv()

ASSETS_PATH = (Path(__file__).parent / "front" / "assets").resolve()
DEFAULT_UPLOAD_DIR = (Path(__file__).parent / "uploads").resolve()

def main(page: ft.Page):
    def route_change(e: ft.RouteChangeEvent):
        page.views.clear()

        if page.route in ("/", "", None):
            print("Inicia")
            page.views.append(login_view(page))

        elif page.route == "/loading":
            from front.ventana_cargando import loading_view
            page.views.append(loading_view(page))

        elif page.route == "/sheets":
            from front.ventana_sheets import sheets_selector_view
            page.views.append(sheets_selector_view(page))

        elif page.route == "/panel_window":
            from front.stock.panel_window import panel_window_view
            page.views.append(panel_window_view(page))

        elif page.route == "/panel":
            page.go("/panel_window")
            return

        else:
            page.views.append(login_view(page))

        page.update()

    page.on_route_change = route_change
    page.go("/")  # arranca en login


if __name__ == "__main__":
    # ---- Configurar variables de entorno para uploads WEB ----
    # Clave para firmar URLs de subida (aleatoria si no existe):
    os.environ.setdefault("FLET_SECRET_KEY", secrets.token_urlsafe(32))

    # Carpeta donde el servidor guarda archivos subidos en modo web:
    upload_dir = Path(os.getenv("FLET_UPLOAD_DIR") or DEFAULT_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("FLET_UPLOAD_DIR", str(upload_dir))

    # (Opcional) logs rápidos
    # print("[FLET] FLET_UPLOAD_DIR =", os.environ["FLET_UPLOAD_DIR"])
    # print("[FLET] FLET_SECRET_KEY set =", "yes" if os.environ.get("FLET_SECRET_KEY") else "no")

    ft.app(
        target=main,
        assets_dir=str(ASSETS_PATH),
        host="0.0.0.0",
        port=8550,
        view=None,   # server/web
        # NOTA: en esta versión NO pasamos secret_key/upload_dir por kwargs;
        # flet_web los toma de las variables de entorno configuradas arriba.
    )
