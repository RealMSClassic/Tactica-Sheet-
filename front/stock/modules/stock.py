# back/sheet/gestor/gestorMain.py
import flet as ft

PRIMARY = "#4B39EF"
WHITE = ft.Colors.WHITE
BG = ft.Colors.WHITE
TXT = ft.Colors.BLACK87
TXT_MUTED = ft.Colors.BLUE_GREY_600
CARD_BG = ft.Colors.GREY_100

def _product_card(image_url: str, title: str) -> ft.Control:
    return ft.Container(
        bgcolor=CARD_BG,
        border_radius=12,
        padding=8,
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=70, height=70, border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Image(src=image_url, fit=ft.ImageFit.COVER),
                ),
                ft.Container(width=16),
                ft.Text(title, size=16, color=TXT),
            ],
        ),
    )

def _tab_stock() -> ft.Control:
    return ft.Column(
        scroll=ft.ScrollMode.ADAPTIVE,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Text("Stock", size=24, weight=ft.FontWeight.W_600, color=TXT),
            ft.Container(height=8),
            _product_card(
                "https://static.nike.com/a/images/c_limit,w_592,f_auto/t_product_v1/7c5678f4-c28d-4862-a8d9-56750f839f12/zion-1-basketball-shoes-bJ0hLJ.png",
                "Limited Edition",
            ),
            ft.Container(height=12),
            _product_card(
                "https://static.nike.com/a/images/c_limit,w_592,f_auto/t_product_v1/cd1fc4e4-5d02-4f18-afd7-a1ea42ff1f73/sportswear-club-fleece-pullover-hoodie-Gw4Nwq.png",
                "Outerwear",
            ),
        ],
    )

def _tab_deposito(page: ft.Page) -> ft.Control:
    def on_add(_):
        page.snack_bar = ft.SnackBar(ft.Text("Agregar (Depósito) – acción no implementada"))
        page.snack_bar.open = True
        page.update()

    return ft.Column(
        scroll=ft.ScrollMode.ADAPTIVE,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Text("Depositos", size=24, weight=ft.FontWeight.W_600, color=TXT),
            ft.Container(height=8),
            _product_card(
                "https://static.nike.com/a/images/c_limit,w_592,f_auto/t_product_v1/7c5678f4-c28d-4862-a8d9-56750f839f12/zion-1-basketball-shoes-bJ0hLJ.png",
                "Limited Edition",
            ),
            ft.Container(height=12),
            _product_card(
                "https://static.nike.com/a/images/c_limit,w_592,f_auto/t_product_v1/cd1fc4e4-5d02-4f18-afd7-a1ea42ff1f73/sportswear-club-fleece-pullover-hoodie-Gw4Nwq.png",
                "Outerwear",
            ),
            ft.Container(height=16),
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.FilledButton(
                        "Agregar",
                        style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=on_add,
                        height=40,
                    )
                ],
            ),
        ],
    )

def _tab_items(page: ft.Page) -> ft.Control:
    def on_add(_):
        page.snack_bar = ft.SnackBar(ft.Text("Agregar (Items) – acción no implementada"))
        page.snack_bar.open = True
        page.update()

    return ft.Column(
        scroll=ft.ScrollMode.ADAPTIVE,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Text("Items", size=24, weight=ft.FontWeight.W_600, color=TXT),
            ft.Container(height=8),
            _product_card(
                "https://static.nike.com/a/images/c_limit,w_592,f_auto/t_product_v1/cd1fc4e4-5d02-4f18-afd7-a1ea42ff1f73/sportswear-club-fleece-pullover-hoodie-Gw4Nwq.png",
                "Outerwear",
            ),
            ft.Container(height=12),
            _product_card(
                "https://static.nike.com/a/images/c_limit,w_592,f_auto/t_product_v1/5de4d66e-c076-4bf7-80ca-a220e301cb3a/sportswear-club-fleece-joggers-KflRdQ.png",
                "Pants",
            ),
            ft.Container(height=16),
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.FilledButton(
                        "Agregar",
                        style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE, shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=on_add,
                        height=40,
                    )
                ],
            ),
        ],
    )

def gestor_view(page: ft.Page) -> ft.Control:
    # --- Search handlers (solo UI)
    search = ft.TextField(
        label="Search for your shoes...",
        hint_text="Search for your shoes...",
        filled=True,
        bgcolor=ft.Colors.GREY_100,
        border_radius=12,
        border_color=ft.Colors.GREY_300,
        focused_border_color=PRIMARY,
        prefix_icon=ft.Icons.SEARCH,
        content_padding=ft.padding.symmetric(horizontal=24, vertical=20),
        expand=True,
    )

    def on_search_icon(_):
        page.snack_bar = ft.SnackBar(ft.Text(f"Buscar: {search.value or '(vacío)'}"))
        page.snack_bar.open = True
        page.update()

    # --- Top bar (equivalente al AppBar “Gestor”)
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Gestor", size=22, color=TXT, weight=ft.FontWeight.W_600),
            ft.Container(width=1),  # placeholder para acciones a futuro
        ],
    )

    search_row = ft.Row(
        controls=[
            search,
            ft.Container(
                padding=ft.padding.only(right=12, left=0, top=12),
                content=ft.IconButton(
                    icon=ft.Icons.SEARCH_SHARP,
                    icon_color=TXT,
                    icon_size=30,
                    on_click=on_search_icon,
                ),
            ),
        ],
    )

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=150,
        tab_alignment=ft.TabAlignment.START,
        scrollable=True,
        divider_color=ft.Colors.TRANSPARENT,
        indicator_color=PRIMARY,
        label_color=PRIMARY,
        unselected_label_color=TXT_MUTED,
        tabs=[
            ft.Tab(text="Stock", content=ft.Container(padding=ft.padding.symmetric(horizontal=16), content=_tab_stock())),
            ft.Tab(text="Deposito", content=ft.Container(padding=ft.padding.symmetric(horizontal=16), content=_tab_deposito(page))),
            ft.Tab(text="Items", content=ft.Container(padding=ft.padding.symmetric(horizontal=16), content=_tab_items(page))),
        ],
        expand=True,
    )

    root = ft.Container(
        bgcolor=BG,
        expand=True,
        padding=16,
        content=ft.Column(
            expand=True,
            spacing=8,
            controls=[
                header,
                ft.Container(padding=ft.padding.only(left=16, right=8), content=search_row),
                ft.Container(height=4),
                ft.Container(expand=True, content=tabs),
            ],
        ),
    )
    return root
