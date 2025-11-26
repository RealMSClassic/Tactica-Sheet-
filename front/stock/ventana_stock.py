# front/ventana_stock.py
import flet as ft


def stock_view(page: ft.Page) -> ft.View:
    # Paleta simple
    RED = "#E53935"
    WHITE = ft.Colors.WHITE
    BG = ft.Colors.GREY_50

    # ------------------ estado en memoria ------------------
    # Datos de ejemplo: podés reemplazarlos por los tuyos
    all_items: list[dict] = [
        {
            "name": "Mouse Inalámbrico",
            "desc": "Mouse óptico 2.4GHz, 1600dpi.",
            "qty": 14,
            "img": "https://images.unsplash.com/photo-1587825140400-5fc8e9f0d16f?q=80&w=600&auto=format&fit=crop",
        },
        {
            "name": "Teclado Mecánico",
            "desc": "Switches blue, layout español.",
            "qty": 8,
            "img": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?q=80&w=600&auto=format&fit=crop",
        },
        {
            "name": "Auriculares",
            "desc": "Over-ear con cancelación de ruido.",
            "qty": 3,
            "img": "https://images.unsplash.com/photo-1518443952248-7db1570d1d9d?q=80&w=600&auto=format&fit=crop",
        },
        {
            "name": "Monitor 24\"",
            "desc": "FHD 75Hz con HDMI.",
            "qty": 21,
            "img": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?q=80&w=600&auto=format&fit=crop",
        },
    ]
    filtered: list[dict] = list(all_items)

    status_txt = ft.Text("", size=12, color=ft.Colors.GREY_600)
    lv = ft.ListView(spacing=10, expand=1, auto_scroll=False)

    # ------------------ UI: buscador ------------------
    search = ft.TextField(
        hint_text="Buscar por nombre…",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED,
        content_padding=12,
        on_change=lambda e: on_search_change(),
    )

    def on_search_change():
        q = (search.value or "").strip().lower()
        filtered.clear()
        if not q:
            filtered.extend(all_items)
        else:
            filtered.extend([it for it in all_items if q in it["name"].lower()])
        refresh_list()

    # ------------------ Render de ítem ------------------
    def qty_badge(qty: int) -> ft.Control:
        # Un "badge" para la cantidad
        tone = ft.Colors.GREY_200 if qty > 0 else ft.Colors.RED_50
        txt_color = ft.Colors.BLACK87 if qty > 0 else ft.Colors.RED
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            bgcolor=tone,
            border_radius=20,
            content=ft.Text(f"Cantidad: {qty}", size=12, color=txt_color, weight=ft.FontWeight.W_600),
        )

    def avatar(img_url: str) -> ft.Control:
        # Imagen circular 44x44
        return ft.Container(
            width=44,
            height=44,
            border_radius=22,
            bgcolor=ft.Colors.GREY_100,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(src=img_url, fit=ft.ImageFit.COVER),
        )

    def build_item(it: dict) -> ft.Control:
        left = avatar(it["img"])

        middle = ft.Column(
            spacing=4,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Text(
                    it["name"],
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.BLACK,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    it["desc"],
                    size=12,
                    color=ft.Colors.GREY_700,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
        )

        right = ft.Column(
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            controls=[
                qty_badge(it["qty"]),
                ft.Icon(name=ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ft.Colors.GREY_500, size=20),
            ],
        )

        card = ft.Container(
            bgcolor=WHITE,
            border_radius=12,
            padding=12,
            shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.GREY_200, spread_radius=0.5),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    left,
                    ft.Container(expand=True, content=middle),
                    right,
                ],
            ),
            on_click=lambda e: page.go("/panel"),
        )
        return card

    # ------------------ refresh de lista ------------------
    def refresh_list():
        lv.controls = []
        for it in filtered:
            lv.controls.append(build_item(it))
            lv.controls.append(ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_200))
        status_txt.value = f"Items: {len(filtered)} / {len(all_items)}"
        page.update()

    # Helper snackbar
    def _sb(txt: str):
        page.snack_bar = ft.SnackBar(ft.Text(txt))
        page.snack_bar.open = True
        page.update()

    page.snack_bar_open = _sb  # por si querés usarlo en callbacks

    # ------------------ layout ------------------
    header = ft.AppBar(
        title=ft.Text("Stock", size=20, weight=ft.FontWeight.W_700, color=WHITE),
        bgcolor=RED,
        center_title=False,
    )

    body = ft.Container(
        bgcolor=BG,
        expand=True,
        content=ft.Column(
            expand=True,
            spacing=8,
            controls=[
                # estado / contador
                ft.Container(padding=ft.padding.only(left=16, right=16, top=10, bottom=0), content=status_txt),
                # buscador
                ft.Container(padding=ft.padding.symmetric(horizontal=16), content=search),
                # lista
                ft.Container(expand=True, padding=ft.padding.only(left=16, right=16, top=8), content=lv),
            ],
        ),
    )

    view = ft.View(
        route="/stock",
        appbar=header,
        controls=[body],
    )

    # Primera carga
    refresh_list()
    return view
