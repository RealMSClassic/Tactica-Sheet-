# back/sheet/tabGestor/tabStock/tabFrontStock.py
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

    # Altura extra para scroll agradable
    extra_h = int(getattr(page, "window_height", 700))
    lv.controls.append(ft.Container(height=extra_h, bgcolor=ft.Colors.TRANSPARENT))

    page.update()


# ========= Paneles (Producto / Depósito) =========

def _open_qty_bs(
    page: ft.Page,
    title: str,
    ok_label: str,
    on_ok: Callable[[int], None],
):
    """BottomSheet genérico para pedir cantidad."""
    t_qty = ft.TextField(
        label="Cantidad",
        width=220,
        value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(allow=True, regex_string=r"[-0-9]", replacement_string=""),
    )
    busy = ft.ProgressBar(visible=False, width=220)
    ok = ft.FilledButton(ok_label, icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
    cancel = ft.OutlinedButton("Cancelar")

    inner = ft.Container(
        padding=16,
        bgcolor=WHITE,
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Text(title, size=16, weight=ft.FontWeight.W_700),
                t_qty,
                busy,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok]),
            ],
        ),
    )
    bs = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
    page.open(bs)

    def _close(_=None):
        try:
            page.close(bs)
        except Exception:
            bs.open = False
        page.update()

    def _ok(_):
        n = 0
        try:
            n = int((t_qty.value or "0").strip())
        except Exception:
            n = 0
        if n < 1:
            page.snack_bar = ft.SnackBar(ft.Text("Cantidad inválida (≥ 1)."))
            page.snack_bar.open = True
            page.update()
            return
        busy.visible = True
        ok.disabled = True
        cancel.disabled = True
        page.update()
        try:
            on_ok(n)
            _close()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
            page.snack_bar.open = True
            page.update()
        finally:
            busy.visible = False
            ok.disabled = False
            cancel.disabled = False
            page.update()

    ok.on_click = _ok
    cancel.on_click = _close


def _open_move_bs(
    page: ft.Page,
    backend,
    *,
    origin_recid: str,          # RecID del depósito origen (NO de la fila de stock)
    origin_name: str,
    prod_name: str,
    on_move: Callable[[str, int], None],  # (dest_depo_recid, qty) -> None
):
    """BottomSheet para mover stock a OTRO depósito."""
    # Armar opciones de destino (todos menos el origen)
    dest_options = [
        ft.dropdown.Option(
            key=d["RecID"], text=f'{d.get("id_deposito","")} — {d.get("nombre_deposito","")}'
        )
        for d in (backend.depositos or [])
        if d.get("RecID") and d.get("RecID") != origin_recid
    ]
    dd_dest = ft.Dropdown(
        label="Depósito destino",
        width=420,
        options=dest_options,
        value=None,
        disabled=(len(dest_options) == 0),
    )
    t_qty = ft.TextField(
        label="Cantidad a mover",
        width=220,
        value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(allow=True, regex_string=r"[-0-9]", replacement_string=""),
    )
    busy = ft.ProgressBar(visible=False, width=420)
    ok = ft.FilledButton(
        "Mover",
        icon=ft.Icons.CHEVRON_RIGHT,
        style=ft.ButtonStyle(bgcolor=RED, color=WHITE),
        disabled=(len(dest_options) == 0),
    )
    cancel = ft.OutlinedButton("Cancelar")

    inner = ft.Container(
        padding=16,
        bgcolor=WHITE,
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Text(f"Mover '{prod_name}'", size=16, weight=ft.FontWeight.W_700),
                ft.Text(f"Desde: {origin_name}", size=12, color=ft.Colors.GREY_700),
                dd_dest, t_qty, busy,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok]),
            ],
        ),
    )
    bs = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
    page.open(bs)

    def _close(_=None):
        try:
            page.close(bs)
        except Exception:
            bs.open = False
        page.update()

    def _ok(_):
        dest = (dd_dest.value or "").strip()
        try:
            n = int((t_qty.value or "0").strip())
        except Exception:
            n = 0
        if not dest:
            page.snack_bar = ft.SnackBar(ft.Text("Elegí depósito destino."))
            page.snack_bar.open = True
            page.update()
            return
        if dest == origin_recid:
            page.snack_bar = ft.SnackBar(ft.Text("El destino debe ser distinto del origen."))
            page.snack_bar.open = True
            page.update()
            return
        if n < 1:
            page.snack_bar = ft.SnackBar(ft.Text("Cantidad inválida (≥ 1)."))
            page.snack_bar.open = True
            page.update()
            return
        busy.visible = True
        ok.disabled = True
        cancel.disabled = True
        page.update()
        try:
            on_move(dest, n)
            _close()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
            page.snack_bar.open = True
            page.update()
        finally:
            busy.visible = False
            ok.disabled = False
            cancel.disabled = False
            page.update()

    ok.on_click = _ok
    cancel.on_click = _close


def _open_product_panel(page: ft.Page, backend, prod_recid: str, on_after_ops: Callable[[], None]):
    """Panel por PRODUCTO: lista depósitos con ese producto y acciones."""
    rows_prod = backend.rows_for_product(prod_recid)
    prod = backend.prod_by_recid.get(prod_recid, {}) or {}
    nombre_prod = prod.get("nombre_producto", "") or "(producto desconocido)"
    codigo_prod = prod.get("codigo_producto", "") or "-"

    selected_row: Dict | None = None
    list_col = ft.Column(spacing=8, expand=True)
    row_wrappers: List[ft.Container] = []

    def make_row_item(row: Dict):
        d = backend.depo_by_recid.get(row.get("ID_deposito", ""), {}) or {}
        nom_depo = d.get("nombre_deposito", "") or "(depósito desconocido)"
        id_depo = d.get("id_deposito", "") or "-"
        qty = row.get("cantidad", "0") or "0"

        chip = ft.Container(
            bgcolor=ft.Colors.GREY_50, border_radius=8, padding=10,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(nom_depo, size=14, weight=ft.FontWeight.W_600),
                            ft.Text(f"ID: {id_depo}", size=11, color=ft.Colors.GREY_600),
                        ]
                    ),
                    ft.Text(str(qty), size=16, weight=ft.FontWeight.W_700),
                ],
            ),
        )
        wrapper = ft.Container(content=chip)
        wrapper.data = row
        row_wrappers.append(wrapper)

        def on_select(_):
            nonlocal selected_row
            selected_row = wrapper.data
            for w in row_wrappers:
                w.border = None
            wrapper.border = ft.border.all(2, ft.Colors.BLUE_300)
            btn_add.disabled = False
            btn_out.disabled = False
            btn_move.disabled = False
            page.update()

        wrapper.on_click = on_select
        return wrapper

    for rp in rows_prod:
        list_col.controls.append(make_row_item(rp))

    btn_add = ft.FilledButton("Agregar", icon=ft.Icons.ADD, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)
    btn_move = ft.FilledButton("Mover", icon=ft.Icons.SWAP_HORIZ, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)
    btn_out = ft.FilledButton("Descargar", icon=ft.Icons.REMOVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)

    content = ft.Container(
        padding=16,
        bgcolor=ft.Colors.GREY_50,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text(nombre_prod, size=18, weight=ft.FontWeight.W_700),
                ft.Text(f"Código: {codigo_prod}", size=12, color=ft.Colors.GREY_700),
                ft.Divider(),
                ft.Text("Depósitos del producto", size=14, weight=ft.FontWeight.W_600),
                list_col,
                ft.Divider(),
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_EVENLY, controls=[btn_add, btn_move, btn_out]),
            ],
        ),
    )
    bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True, elevation=8)
    page.open(bs)

    def _close_bs(_=None):
        try:
            page.close(bs)
        except Exception:
            bs.open = False
        page.update()

    # --- Acciones ---
    def on_add(_=None):
        if not selected_row:
            page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un depósito."))
            page.snack_bar.open = True
            page.update()
            return
        r = selected_row
        depo = backend.depo_by_recid.get(r.get("ID_deposito", ""), {}) or {}
        depo_name = depo.get("nombre_deposito", "") or "(depósito desconocido)"

        def _do(n: int):
            okb = backend.add_qty(r.get("RecID", ""), n, nombre_prod, depo_name)
            if not okb:
                raise ValueError("No se pudo agregar stock.")
            backend.refresh_all()
            on_after_ops()
            _close_bs()
            page.snack_bar = ft.SnackBar(ft.Text("Stock agregado."))
            page.snack_bar.open = True
            page.update()

        _open_qty_bs(page, "Agregar cantidad", "Agregar", _do)

    def on_out(_=None):
        if not selected_row:
            page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un depósito."))
            page.snack_bar.open = True
            page.update()
            return
        r = selected_row
        depo = backend.depo_by_recid.get(r.get("ID_deposito", ""), {}) or {}
        depo_name = depo.get("nombre_deposito", "") or "(depósito desconocido)"

        def _do(n: int):
            okb = backend.descargar(r.get("RecID", ""), n, nombre_prod, depo_name)
            if not okb:
                raise ValueError("Stock insuficiente.")
            backend.refresh_all()
            on_after_ops()
            _close_bs()
            page.snack_bar = ft.SnackBar(ft.Text("Descarga realizada."))
            page.snack_bar.open = True
            page.update()

        _open_qty_bs(page, "Descargar cantidad", "Descargar", _do)

    def on_move(_=None):
        if not selected_row:
            page.snack_bar = ft.SnackBar(ft.Text("Elegí depósito origen en la lista."))
            page.snack_bar.open = True
            page.update()
            return
        r = selected_row
        origin_recid = r.get("ID_deposito", "")
        origin_name = (backend.depo_by_recid.get(origin_recid, {}) or {}).get("nombre_deposito", "") or "(depósito desconocido)"

        def _do(dest_recid: str, n: int):
            dest_d = backend.depo_by_recid.get(dest_recid, {}) or {}
            dest_name = dest_d.get("nombre_deposito", "") or "(depósito desconocido)"
            okb = backend.move_add_row(r.get("RecID", ""), dest_recid, n, nombre_prod, origin_name, dest_name)
            if not okb:
                raise ValueError("No se pudo mover: verifique cantidad y depósitos.")
            backend.refresh_all()
            on_after_ops()
            _close_bs()
            page.snack_bar = ft.SnackBar(ft.Text("Movimiento realizado (nueva fila creada)."))
            page.snack_bar.open = True
            page.update()

        _open_move_bs(page, backend, origin_recid=origin_recid, origin_name=origin_name, prod_name=nombre_prod, on_move=_do)

    btn_add.on_click = on_add
    btn_out.on_click = on_out
    btn_move.on_click = on_move


def _open_deposito_panel(page: ft.Page, backend, depo_recid: str, on_after_ops: Callable[[], None]):
    """Panel por DEPÓSITO: lista items en ese depósito y acciones."""
    rows_depo = backend.rows_for_deposito(depo_recid)
    depo = backend.depo_by_recid.get(depo_recid, {}) or {}
    nombre_depo = depo.get("nombre_deposito", "") or "(depósito desconocido)"
    id_depo = depo.get("id_deposito", "") or "-"

    selected_row: Dict | None = None
    list_col = ft.Column(spacing=8, expand=True)
    row_wrappers: List[ft.Container] = []

    def make_row_item(row: Dict):
        p = backend.prod_by_recid.get(row.get("ID_producto", ""), {}) or {}
        nombre_prod = p.get("nombre_producto", "") or "(producto desconocido)"
        codigo_prod = p.get("codigo_producto", "") or "-"
        qty = row.get("cantidad", "0") or "0"

        chip = ft.Container(
            bgcolor=ft.Colors.GREY_50, border_radius=8, padding=10,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(nombre_prod, size=14, weight=ft.FontWeight.W_600),
                            ft.Text(f"Código: {codigo_prod}", size=11, color=ft.Colors.GREY_600),
                        ]
                    ),
                    ft.Text(str(qty), size=16, weight=ft.FontWeight.W_700),
                ],
            ),
        )
        wrapper = ft.Container(content=chip)
        wrapper.data = row
        row_wrappers.append(wrapper)

        def on_select(_):
            nonlocal selected_row
            selected_row = wrapper.data
            for w in row_wrappers:
                w.border = None
            wrapper.border = ft.border.all(2, ft.Colors.BLUE_300)
            btn_add.disabled = False
            btn_out.disabled = False
            btn_move.disabled = False
            page.update()

        wrapper.on_click = on_select
        return wrapper

    for rp in rows_depo:
        list_col.controls.append(make_row_item(rp))

    btn_add = ft.FilledButton("Agregar", icon=ft.Icons.ADD, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)
    btn_move = ft.FilledButton("Mover", icon=ft.Icons.SWAP_HORIZ, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)
    btn_out = ft.FilledButton("Descargar", icon=ft.Icons.REMOVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)

    content = ft.Container(
        padding=16,
        bgcolor=ft.Colors.GREY_50,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text(nombre_depo, size=18, weight=ft.FontWeight.W_700),
                ft.Text(f"ID: {id_depo}", size=12, color=ft.Colors.GREY_700),
                ft.Divider(),
                ft.Text("Items en el depósito", size=14, weight=ft.FontWeight.W_600),
                list_col,
                ft.Divider(),
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_EVENLY, controls=[btn_add, btn_move, btn_out]),
            ],
        ),
    )
    bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True, elevation=8)
    page.open(bs)

    def _close_bs(_=None):
        try:
            page.close(bs)
        except Exception:
            bs.open = False
        page.update()

    # --- Acciones ---
    def on_add(_=None):
        if not selected_row:
            page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un item de la lista."))
            page.snack_bar.open = True
            page.update()
            return
        r = selected_row

        def _do(n: int):
            okb = backend.add_qty(r.get("RecID", ""), n, "", nombre_depo)
            if not okb:
                raise ValueError("No se pudo agregar stock.")
            backend.refresh_all()
            on_after_ops()
            _close_bs()
            page.snack_bar = ft.SnackBar(ft.Text("Stock agregado."))
            page.snack_bar.open = True
            page.update()

        _open_qty_bs(page, "Agregar cantidad", "Agregar", _do)

    def on_out(_=None):
        if not selected_row:
            page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un item de la lista."))
            page.snack_bar.open = True
            page.update()
            return
        r = selected_row

        def _do(n: int):
            okb = backend.descargar(r.get("RecID", ""), n, "", nombre_depo)
            if not okb:
                raise ValueError("Stock insuficiente.")
            backend.refresh_all()
            on_after_ops()
            _close_bs()
            page.snack_bar = ft.SnackBar(ft.Text("Descarga realizada."))
            page.snack_bar.open = True
            page.update()

        _open_qty_bs(page, "Descargar cantidad", "Descargar", _do)

    def on_move(_=None):
        if not selected_row:
            page.snack_bar = ft.SnackBar(ft.Text("Elegí el item origen en la lista."))
            page.snack_bar.open = True
            page.update()
            return
        r = selected_row
        origin_recid = r.get("ID_deposito", "")
        origin_name = nombre_depo

        # Nombre de producto (opcional, solo para el log descriptivo)
        p = backend.prod_by_recid.get(r.get("ID_producto", ""), {}) or {}
        prod_name = p.get("nombre_producto", "") or "(producto)"

        def _do(dest_recid: str, n: int):
            dest_d = backend.depo_by_recid.get(dest_recid, {}) or {}
            dest_name = dest_d.get("nombre_deposito", "") or "(depósito)"
            okb = backend.move_add_row(r.get("RecID", ""), dest_recid, n, prod_name, origin_name, dest_name)
            if not okb:
                raise ValueError("No se pudo mover: verifique cantidad y depósitos.")
            backend.refresh_all()
            on_after_ops()
            _close_bs()
            page.snack_bar = ft.SnackBar(ft.Text("Movimiento realizado (nueva fila creada)."))
            page.snack_bar.open = True
            page.update()

        _open_move_bs(page, backend, origin_recid=origin_recid, origin_name=origin_name, prod_name=prod_name, on_move=_do)

    btn_add.on_click = on_add
    btn_out.on_click = on_out
    btn_move.on_click = on_move


# ========= Vista principal =========

def build_stock_tab(
    page: ft.Page,
    backend,
    bus: Optional[object] = None,
    initial_view: str = "stock",
    initial_sort: str = "name_asc",
) -> ft.Control:
    """
    Barra ÚNICA:
      - Buscador (texto)
      - Toggle Stock/Depósito
      - Filtros: A–Z, Z–A, Cantidad ↑, Cantidad ↓
    Lista compacta SIN imágenes. Compatible con gestorMain.
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

    # Toggle incrustado
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

    # Filtros
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

    # Buscador
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

    # Callbacks: ahora abren los paneles
    def _open_product(pid: str):
        _open_product_panel(page, backend, pid, on_after_ops=_render)

    def _open_deposito(did: str):
        _open_deposito_panel(page, backend, did, on_after_ops=_render)

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

    # Header
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[ft.Text("Stock", size=22, weight=ft.FontWeight.W_700), status],
    )

    # Barra única
    topbar = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=8,
        controls=[search, ft.Row(spacing=8, controls=[toggle_holder, filter_btn])],
    )

    # Altura mínima (~8 filas)
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
    if bus:
        try:
            bus.subscribe("productos_changed", lambda _d: (backend.refresh_products(), _render()))
            bus.subscribe("depositos_changed", lambda _d: (backend.refresh_depositos(), _render()))
            bus.subscribe("stock_changed", lambda _d: (backend.refresh_stock(), _render()))
        except Exception:
            pass

    return root
