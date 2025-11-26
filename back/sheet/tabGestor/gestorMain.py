# back/sheet/tabGestor/gestorMain.py
from __future__ import annotations
import flet as ft
from back.sheet.tabGestor.event_bus import EventBus

# Depósito
from back.sheet.tabGestor.tabDeposito.tabBackDeposito import DepositoBackend
from back.sheet.tabGestor.tabDeposito.tabFrontDeposito import build_deposito_tab

# Items
from back.sheet.tabGestor.tabItems.tabBackItems import ItemsBackend
from back.sheet.tabGestor.tabItems.tabFrontItems import build_items_tab

# Stock
from back.sheet.tabGestor.tabStock.tabBackStock import StockBackend
from back.sheet.tabGestor.tabStock.tabFrontStock import build_stock_tab

PRIMARY = "#4B39EF"
WHITE = ft.Colors.WHITE
BG = ft.Colors.WHITE
TXT = ft.Colors.BLACK87
TXT_MUTED = ft.Colors.BLUE_GREY_600


def gestor_view(page: ft.Page) -> ft.Control:
    bus = EventBus()

    # Backends
    depo_backend  = DepositoBackend(page, bus=bus)
    items_backend = ItemsBackend(page, bus=bus)
    stock_backend = StockBackend(page, bus=bus, depo_backend=depo_backend, items_backend=items_backend)

    # Tab Stock
    try:
        stock_content = build_stock_tab(page, stock_backend, bus=bus)
    except Exception as e:
        stock_content = ft.Container(
            expand=True, padding=16, content=ft.Text(f"Error Stock: {e}", color=ft.Colors.RED_700)
        )

    # Tab Depósito
    try:
        deposito_content = ft.Container(
            expand=True,
            padding=ft.padding.symmetric(horizontal=16),
            content=build_deposito_tab(page, depo_backend, bus=bus),
        )
    except Exception as e:
        deposito_content = ft.Container(
            expand=True, padding=16, content=ft.Text(f"Error Depósito: {e}", color=ft.Colors.RED_700)
        )

    # Tab Items
    try:
        items_content = ft.Container(
            expand=True,
            padding=ft.padding.symmetric(horizontal=16),
            content=build_items_tab(page, items_backend, bus=bus),
        )
    except Exception as e:
        items_content = ft.Container(
            expand=True, padding=16, content=ft.Text(f"Error Items: {e}", color=ft.Colors.RED_700)
        )

    tabs = ft.Tabs(
        selected_index=0,  # primero: Stock
        animation_duration=150,
        tab_alignment=ft.TabAlignment.START,
        scrollable=True,
        divider_color=ft.Colors.TRANSPARENT,
        indicator_color=PRIMARY,
        label_color=PRIMARY,
        unselected_label_color=TXT_MUTED,
        tabs=[
            ft.Tab(text="Stock",    content=stock_content),
            ft.Tab(text="Depósito", content=deposito_content),
            ft.Tab(text="Items",    content=items_content),
        ],
        expand=True,
    )

    return ft.Container(
        bgcolor=BG,
        expand=True,
        padding=16,
        content=ft.Column(
            expand=True,
            spacing=8,
            controls=[ft.Container(expand=True, content=tabs)],
        ),
    )
