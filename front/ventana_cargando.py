# front/ventana_cargando.py
import time
import flet as ft

AUTH_WINDOW_SEC = 120  # igual que en login/main

def _cs_get(page: ft.Page, key: str):
    try:
        return page.client_storage.get(key)
    except Exception:
        return page.session.get(key)

def _is_auth_in_progress(page: ft.Page) -> bool:
    flag = _cs_get(page, "auth_in_progress")
    ts = _cs_get(page, "auth_started_at")
    try:
        tsf = float(ts) if ts is not None else None
    except Exception:
        tsf = None
    if (flag == "1" or flag is True) and tsf is not None:
        return (time.time() - tsf) < AUTH_WINDOW_SEC
    return False

def _go_soon(page: ft.Page, route: str):
    import asyncio
    async def _t():
        await asyncio.sleep(0)
        page.go(route)
    page.run_task(_t)

def loading_view(page: ft.Page) -> ft.View:
    has_auth = bool(getattr(page.auth, "token", None) or page.session.get("id_token"))
    in_progress = _is_auth_in_progress(page)

    # Navegación suave según estado
    if has_auth:
        _go_soon(page, "/sheets")
    elif not in_progress:
        _go_soon(page, "/")

    # ---- UI (mismo diseño que ventana_login, sin botón) ----
    logo = ft.Image(src="logo.png", width=180, height=180, fit=ft.ImageFit.CONTAIN)
    title = ft.Text("Táctica Sheet", size=36, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87)
    subtitle = ft.Text("Gestor de Stocks", size=14, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_GREY_600)

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
                    # Parte superior: logo + títulos (idéntico a login)
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
                            ],
                        ),
                    ),
                    # Parte inferior: solo el cargando (sin botón)
                    ft.Container(
                        padding=ft.padding.only(left=16, right=16, bottom=84),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    controls=[
                                        ft.ProgressRing(),
                                        ft.Container(width=10),
                                        ft.Text("Conectando con Google...", size=14, color=ft.Colors.BLUE_GREY_600),
                                    ],
                                )
                            ],
                        ),
                    ),
                ],
            ),
        ),
    )

    return ft.View(route="/loading", controls=[ui])
