import flet as ft

LOGO_URL = "https://www.tacticasoft.com/wp-content/uploads/2023/01/cropped-logo.png"

def splash_view(page: ft.Page) -> ft.View:
    # Solo muestra el logo centrado sobre fondo blanco
    return ft.View(
        route="/splash",
        controls=[
            ft.Container(
                expand=True,
                bgcolor=ft.Colors.WHITE,
                alignment=ft.alignment.center,
                content=ft.Image(src=LOGO_URL, width=140, height=140, fit=ft.ImageFit.CONTAIN),
            )
        ],
    )
