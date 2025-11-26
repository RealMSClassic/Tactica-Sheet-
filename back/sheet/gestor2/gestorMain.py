# ./back/sheet/gestor/gestorMain.py
import flet as ft
from back.sheet.gestor.tabBackStock import StockBackend
from back.sheet.gestor.tabFrontStock import build_stock_tab
from back.sheet.gestor.tabBackDeposito import DepositoBackend
from back.sheet.gestor.tabFrontDeposito import build_deposito_tab
from back.sheet.gestor.tabBackItems import ItemsBackend
from back.sheet.gestor.tabFrontItems import build_items_tab
from back.sheet.gestor.event_bus import EventBus
from back.sheet.gestor.tabFrontTest import build_test_tab
PRIMARY = "#4B39EF"
WHITE = ft.Colors.WHITE
BG = ft.Colors.WHITE
TXT = ft.Colors.BLACK87
TXT_MUTED = ft.Colors.BLUE_GREY_600

def gestor_view(page: ft.Page) -> ft.Control:
    bus = EventBus()

    stock_backend = StockBackend(page, bus=bus)
    depo_backend  = DepositoBackend(page, bus=bus)
    items_backend = ItemsBackend(page, bus=bus)

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[ft.Text("Gestor", size=22, color=TXT, weight=ft.FontWeight.W_600)],
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
            ft.Tab(
                text="Stock",
                content=ft.Container(
                    expand=True,                # ⬅️ ocupa todo el ancho/alto disponible
                    padding=0,   
                    content=build_stock_tab(page, stock_backend, bus=bus),
                ),
            ),
            ft.Tab(
                text="Deposito",
                content=ft.Container(
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=16),
                    content=build_deposito_tab(page, depo_backend, bus=bus),
                ),
            ),
            ft.Tab(
                text="Items",
                content=ft.Container(
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=16),
                    content=build_items_tab(page, items_backend, bus=bus),
                ),
            ),
            ft.Tab(text="Test (Images)", content=build_test_tab(page, backend=None, bus=bus)),
        ],
        expand=True,  # ⬅️ hace que el control Tabs ocupe todo el alto disponible
    )

    # El root ocupa toda la pantalla; las pestañas expanden dentro.
    return ft.Container(
        bgcolor=BG,
        expand=True,
        padding=16,
        content=ft.Column(
            expand=True,
            spacing=8,
            controls=[
                header,
                ft.Container(expand=True, content=tabs),  # ⬅️ tabs a pantalla completa
            ],
        ),
    )
