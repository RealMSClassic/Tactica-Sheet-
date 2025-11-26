# back/sheet/tabGestor/tabStock/listaStock.py
from __future__ import annotations
import flet as ft
from typing import Dict, List, Optional, Callable

# ===== Estilo base (sin imágenes) =====
ROW_HEIGHT = 88
ROW_SPACING = 8
MIN_ROWS_VISIBLE = 8
MIN_LIST_HEIGHT = ROW_HEIGHT * MIN_ROWS_VISIBLE + ROW_SPACING * (MIN_ROWS_VISIBLE - 1)

RED = "#E53935"
WHITE = ft.Colors.WHITE


# ====== ORDENAMIENTO ======
def _apply_sort(grouped: List[Dict], mode: str, sort_mode: str, backend) -> List[Dict]:
    def name_key(g: Dict) -> str:
        if mode == "stock":
            p = backend.prod_by_recid.get(g["ID_producto"], {})
            return (p.get("nombre_producto") or "").lower()
        else:
            d = backend.depo_by_recid.get(g["ID_deposito"], {})
            return (d.get("nombre_deposito") or "").lower()

    def qty_key(g: Dict) -> int:
        try:
            return int(g.get("total", 0))
        except Exception:
            return 0

    if sort_mode == "name_asc":
        return sorted(grouped, key=name_key)
    if sort_mode == "name_desc":
        return sorted(grouped, key=name_key, reverse=True)
    if sort_mode == "qty_asc":
        return sorted(grouped, key=qty_key)
    if sort_mode == "qty_desc":
        return sorted(grouped, key=qty_key, reverse=True)
    return grouped


# ====== RENDER LISTA (sin imágenes) ======
def render_stock_list(
    *,
    page: ft.Page,
    backend,
    lv: ft.ListView,
    status: ft.Text,
    query_text: str,
    view_mode_value: str,         # "stock" | "deposito"
    sort_mode_value: str,         # name_asc|name_desc|qty_asc|qty_desc
    on_open_product: Callable[[str], None],
    on_open_deposito: Callable[[str], None],
):
    lv.controls.clear()
    q = (query_text or "").strip().lower()

    if view_mode_value == "stock":
        grouped = backend.filter_grouped_by_product(q)
        grouped = _apply_sort(grouped, "stock", sort_mode_value, backend)
        total = sum(g.get("total", 0) for g in grouped) if grouped else 0

        for g in grouped:
            pid = g["ID_producto"]
            p = backend.prod_by_recid.get(pid, {}) or {}
            nombre_prod = p.get("nombre_producto", "") or "(producto desconocido)"
            codigo_prod = p.get("codigo_producto", "") or "-"

            def _open(_=None, _pid=pid):
                on_open_product(_pid)

            lv.controls.append(
                ft.Container(
                    on_click=_open,
                    ink=True,
                    bgcolor=WHITE,
                    border_radius=10,
                    padding=12,
                    height=ROW_HEIGHT,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=2,
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(nombre_prod, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87),
                                    ft.Text(f"Código: {codigo_prod}", size=12, color=ft.Colors.GREY_700),
                                ],
                            ),
                            ft.Text(str(g.get("total", 0)), size=18, weight=ft.FontWeight.W_700, color=ft.Colors.BLACK87),
                        ],
                    ),
                )
            )

        status.value = f"Productos: {len(grouped)} | Total unidades: {total}"

    else:
        grouped = backend.filter_grouped_by_deposito(q)
        grouped = _apply_sort(grouped, "deposito", sort_mode_value, backend)
        total = sum(g.get("total", 0) for g in grouped) if grouped else 0

        for g in grouped:
            did = g["ID_deposito"]
            d = backend.depo_by_recid.get(did, {}) or {}
            nombre_depo = d.get("nombre_deposito", "") or "(depósito desconocido)"
            id_depo = d.get("id_deposito", "") or "-"

            def _open(_=None, _did=did):
                on_open_deposito(_did)

            lv.controls.append(
                ft.Container(
                    on_click=_open,
                    ink=True,
                    bgcolor=WHITE,
                    border_radius=10,
                    padding=12,
                    height=ROW_HEIGHT,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Column(
                                spacing=2,
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(nombre_depo, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87),
                                    ft.Text(f"ID: {id_depo}", size=12, color=ft.Colors.GREY_700),
                                ],
                            ),
                            ft.Text(str(g.get("total", 0)), size=18, weight=ft.FontWeight.W_700, color=ft.Colors.BLACK87),
                        ],
                    ),
                )
            )

        status.value = f"Depósitos: {len(grouped)} | Total unidades: {total}"

    # Spacer de “una página” para alargar el scroll
    extra_h = int(getattr(page, "window_height", 700))
    lv.controls.append(ft.Container(height=extra_h, bgcolor=ft.Colors.TRANSPARENT))

    page.update()


# ====== TAB (UNA SOLA BARRA: buscador + toggle + filtros) ======
def build_stock_tab(
    page: ft.Page,
    backend,
    bus: Optional[object] = None,
    initial_view: str = "stock",
    initial_sort: str = "name_asc",
) -> ft.Control:
    """
    Barra superior única con:
      - Buscador
      - Toggle Stock/Depósito (en el mismo row)
      - Filtros: A–Z, Z–A, Cantidad ↑, Cantidad ↓
    Lista sin imágenes para ambas vistas.
    """
    # Conectar page si hace falta
    if getattr(backend, "attach_page", None) and getattr(backend, "page", None) is None:
        backend.attach_page(page)

    # Estado
    view_mode = {"value": initial_view}     # "stock" | "deposito"
    sort_mode = {"value": initial_sort}     # "name_asc" | "name_desc" | "qty_asc" | "qty_desc"

    # Controles base
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)
    lv = ft.ListView(spacing=ROW_SPACING, expand=True, auto_scroll=False)

    # Toggle dentro de la misma barra
    def _segment(label: str, active: bool) -> ft.Container:
        return ft.Container(
            bgcolor=RED if active else ft.Colors.TRANSPARENT,
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            border_radius=8,
            content=ft.Text(
                label,
                size=12,
                weight=ft.FontWeight.W_600,
                color=WHITE if active else ft.Colors.BLACK87,
            ),
        )

    def _paint_toggle() -> ft.Container:
        is_stock = view_mode["value"] == "stock"
        return ft.Container(
            bgcolor=ft.Colors.GREY_100,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=999,
            padding=4,
            on_click=lambda _: _toggle_mode(),
            content=ft.Row(
                spacing=4,
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                controls=[_segment("Stock", is_stock), _segment("Depósito", not is_stock)],
            ),
        )

    toggle_holder = ft.Container(content=_paint_toggle())

    def _toggle_mode():
        view_mode["value"] = "deposito" if view_mode["value"] == "stock" else "stock"
        toggle_holder.content = _paint_toggle()
        _render()

    # Filtros (popup) dentro de la barra
    def _set_sort(sm: str):
        sort_mode["value"] = sm
        _render()

    filter_btn = ft.PopupMenuButton(
        icon=ft.Icons.FILTER_LIST,
        tooltip="Ordenar",
        items=[
            ft.PopupMenuItem(text="Nombre A–Z", on_click=lambda _: _set_sort("name_asc")),
            ft.PopupMenuItem(text="Nombre Z–A", on_click=lambda _: _set_sort("name_desc")),
            ft.PopupMenuItem(text="Cantidad ↑", on_click=lambda _: _set_sort("qty_asc")),
            ft.PopupMenuItem(text="Cantidad ↓", on_click=lambda _: _set_sort("qty_desc")),
        ],
    )

    # Buscador: cuando cambia, re-render
    search = ft.TextField(
        hint_text="Buscar...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED,
        content_padding=10,
        on_change=lambda _: _render(),
        expand=True,
    )

    # Acciones por fila (callbacks que podés reemplazar desde fuera si querés)
    def _open_product(pid: str):
        print(f"[UI] Abrir producto: {pid}")

    def _open_deposito(did: str):
        print(f"[UI] Abrir depósito: {did}")

    # Render principal
    def _render():
        render_stock_list(
            page=page,
            backend=backend,
            lv=lv,
            status=status,
            query_text=search.value or "",
            view_mode_value=view_mode["value"],
            sort_mode_value=sort_mode["value"],
            on_open_product=_open_product,
            on_open_deposito=_open_deposito,
        )

    # Header (título + estado)
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[ft.Text("Stock", size=22, weight=ft.FontWeight.W_700), status],
    )

    # === BARRA ÚNICA: Buscador + Toggle + Filtros ===
    topbar = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=8,
        controls=[
            search,                               # buscador (expand)
            ft.Row(spacing=8, controls=[toggle_holder, filter_btn]),
        ],
    )

    # Holder con altura mínima (~8 filas)
    lv_holder = ft.Stack(
        expand=True,
        controls=[
            ft.Container(height=MIN_LIST_HEIGHT, bgcolor=ft.Colors.TRANSPARENT),
            ft.Container(expand=True, content=lv),
        ],
    )

    root = ft.Container(
        bgcolor=ft.Colors.GREY_50,
        expand=True,
        border_radius=12,
        padding=16,
        content=ft.Column(
            spacing=10,
            expand=True,
            controls=[header, topbar, lv_holder],
        ),
    )

    # Carga inicial + primer render
    try:
        backend.refresh_all()
    except Exception as e:
        print("[ERROR] refresh_all:", e)

    toggle_holder.content = _paint_toggle()
    _render()

    # Suscripciones (si hay bus)
    if getattr(backend, "bus", None):
        try:
            backend.bus.subscribe("productos_changed", lambda _d: (backend.refresh_products(), _render()))
            backend.bus.subscribe("depositos_changed", lambda _d: (backend.refresh_depositos(), _render()))
            backend.bus.subscribe("stock_changed", lambda _d: (backend.refresh_stock(), _render()))
        except Exception:
            pass

    return root
