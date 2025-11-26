# ./back/sheet/gestor/tabFrontStock.py
import flet as ft
from typing import Dict, List, Optional

ROW_HEIGHT = 88
ROW_SPACING = 8
MIN_ROWS_VISIBLE = 8
MIN_LIST_HEIGHT = ROW_HEIGHT * MIN_ROWS_VISIBLE + ROW_SPACING * (MIN_ROWS_VISIBLE - 1)

RED = "#E53935"
WHITE = ft.Colors.WHITE


def build_stock_tab(page: ft.Page, backend, bus: Optional[object] = None) -> ft.Control:
    """
    UI de Stock con:
      - Toggle 'Stock / Depósito' en un solo botón (clic = alterna).
      - Filtro de orden (nombre/cantidad asc/desc).
      - Modo 'Stock': agrupado por producto.
      - Modo 'Depósito': agrupado por depósito; panel lista ITEMS del depósito.
    """
    # Por si el backend se creó sin page
    if getattr(backend, "attach_page", None) and getattr(backend, "page", None) is None:
        backend.attach_page(page)

    # ---- Estado UI ----
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)
    search = ft.TextField(
        hint_text="Buscar...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED,
        content_padding=10,
        on_change=lambda _: render_list(),
    )
    lv = ft.ListView(spacing=ROW_SPACING, expand=True, auto_scroll=False)

    # 'stock' = por producto; 'deposito' = por depósito
    view_mode = {"value": "stock"}
    sort_mode = {"value": "name_asc"}  # name_asc | name_desc | qty_asc | qty_desc

    # ---- Helpers de estilo/estado ----
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

    def _repaint_toggle() -> ft.Container:
        is_stock = view_mode["value"] == "stock"
        return ft.Container(
            bgcolor=ft.Colors.GREY_100,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=999,
            padding=4,
            on_click=lambda _: toggle_mode(),
            content=ft.Row(
                spacing=4,
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                controls=[
                    _segment("Stock", is_stock),
                    _segment("Depósito", not is_stock),
                ],
            ),
        )

    toggle_holder = ft.Container(content=_repaint_toggle())

    def toggle_mode():
        view_mode["value"] = "deposito" if view_mode["value"] == "stock" else "stock"
        toggle_holder.content = _repaint_toggle()
        render_list()

    # ---- Filtro / orden ----
    def set_sort(sm: str):
        sort_mode["value"] = sm
        render_list()

    filter_btn = ft.PopupMenuButton(
        icon=ft.Icons.FILTER_LIST,
        tooltip="Ordenar",
        items=[
            ft.PopupMenuItem(text="Nombre A–Z", on_click=lambda _: set_sort("name_asc")),
            ft.PopupMenuItem(text="Nombre Z–A", on_click=lambda _: set_sort("name_desc")),
            ft.PopupMenuItem(text="Cantidad ↑", on_click=lambda _: set_sort("qty_asc")),
            ft.PopupMenuItem(text="Cantidad ↓", on_click=lambda _: set_sort("qty_desc")),
        ],
    )

    # ---- Cargas ----
    def load_all():
        backend.refresh_all()

    # ---- Ordenamiento ----
    def apply_sort(grouped: List[Dict]) -> List[Dict]:
        mode = view_mode["value"]
        sm = sort_mode["value"]

        def name_key(g: Dict) -> str:
            if mode == "stock":
                p = backend.prod_by_recid.get(g["ID_producto"], {})
                return (p.get("nombre_producto") or "").lower()
            else:
                d = backend.depo_by_recid.get(g["ID_deposito"], {})
                return (d.get("nombre_deposito") or "").lower()

        def qty_key(g: Dict) -> int:
            return int(g.get("total", 0))

        if sm == "name_asc":
            return sorted(grouped, key=name_key)
        if sm == "name_desc":
            return sorted(grouped, key=name_key, reverse=True)
        if sm == "qty_asc":
            return sorted(grouped, key=qty_key)
        if sm == "qty_desc":
            return sorted(grouped, key=qty_key, reverse=True)
        return grouped

    # ---- Render principal ----
    def render_list():
        lv.controls.clear()
        q = (search.value or "").strip().lower()
        mode = view_mode["value"]

        if mode == "stock":
            grouped = backend.filter_grouped_by_product(q)
            grouped = apply_sort(grouped)
            total = sum(g["total"] for g in grouped) if grouped else 0

            for g in grouped:
                p = backend.prod_by_recid.get(g["ID_producto"], {})
                nombre_prod = p.get("nombre_producto", "") or "(producto desconocido)"
                codigo_prod = p.get("codigo_producto", "") or "-"

                def on_click_row(_=None, pid=g["ID_producto"]):
                    open_product_panel(pid)

                lv.controls.append(
                    ft.Container(
                        on_click=on_click_row,
                        ink=True,
                        bgcolor=WHITE,
                        border_radius=10,
                        padding=12,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            nombre_prod,
                                            size=16,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.BLACK87,
                                        ),
                                        ft.Text(
                                            f"Código: {codigo_prod}",
                                            size=12,
                                            color=ft.Colors.GREY_700,
                                        ),
                                    ],
                                ),
                                ft.Text(
                                    str(g["total"]),
                                    size=18,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.BLACK87,
                                ),
                            ],
                        ),
                    )
                )
            status.value = f"Productos: {len(grouped)} | Total unidades: {total}"

        else:
            grouped = backend.filter_grouped_by_deposito(q)
            grouped = apply_sort(grouped)
            total = sum(g["total"] for g in grouped) if grouped else 0

            for g in grouped:
                d = backend.depo_by_recid.get(g["ID_deposito"], {})
                nombre_depo = d.get("nombre_deposito", "") or "(depósito desconocido)"
                id_depo = d.get("id_deposito", "") or "-"

                def on_click_row(_=None, did=g["ID_deposito"]):
                    open_deposito_panel(did)

                lv.controls.append(
                    ft.Container(
                        on_click=on_click_row,
                        ink=True,
                        bgcolor=WHITE,
                        border_radius=10,
                        padding=12,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text(
                                            nombre_depo,
                                            size=16,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.BLACK87,
                                        ),
                                        ft.Text(
                                            f"ID: {id_depo}",
                                            size=12,
                                            color=ft.Colors.GREY_700,
                                        ),
                                    ],
                                ),
                                ft.Text(
                                    str(g["total"]),
                                    size=18,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.BLACK87,
                                ),
                            ],
                        ),
                    )
                )
            status.value = f"Depósitos: {len(grouped)} | Total unidades: {total}"

        # Spacer de “una página” para alargar el scroll
        extra_h = int(getattr(page, "window_height", 700))
        lv.controls.append(ft.Container(height=extra_h, bgcolor=ft.Colors.TRANSPARENT))

        page.update()

    # ---------- Panel por PRODUCTO (lista depósitos de ese producto) ----------
    def open_product_panel(prod_recid: str):
        rows_prod = backend.rows_for_product(prod_recid)

        prod = backend.prod_by_recid.get(prod_recid, {})
        nombre_prod = prod.get("nombre_producto", "") or "(producto desconocido)"
        codigo_prod = prod.get("codigo_producto", "") or "-"

        selected_row: Dict | None = None
        list_col = ft.Column(spacing=8, expand=True)
        row_wrappers: List[ft.Container] = []

        def make_row_item(row: Dict):
            d = backend.depo_by_recid.get(row.get("ID_deposito", ""), {})
            nom_depo = d.get("nombre_deposito", "") or "(depósito desconocido)"
            id_depo = d.get("id_deposito", "") or "-"
            qty = row.get("cantidad", "0") or "0"

            chip = ft.Container(
                bgcolor=ft.Colors.GREY_50,
                border_radius=8,
                padding=10,
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

        btn_add = ft.FilledButton(
            "Agregar", icon=ft.Icons.ADD, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True
        )
        btn_move = ft.FilledButton(
            "Mover", icon=ft.Icons.SWAP_HORIZ, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True
        )
        btn_out = ft.FilledButton(
            "Descargar", icon=ft.Icons.REMOVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True
        )

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
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_EVENLY, controls=[btn_add, btn_move, btn_out]
                    ),
                ],
            ),
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True, elevation=8)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs)
            page.update()

        # --- Acciones reutilizando backend ---
        def do_add_qty(recid_stock: str, depo_name: str):
            def _handler(_):
                t_qty = ft.TextField(
                    label="Cantidad a agregar",
                    width=220,
                    value="1",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    input_filter=ft.InputFilter(allow=True, regex_string=r"[-0-9]", replacement_string=""),
                )
                busy = ft.ProgressBar(visible=False, width=220)
                ok = ft.FilledButton("Agregar", icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
                cancel = ft.OutlinedButton("Cancelar")

                inner = ft.Container(
                    padding=16,
                    bgcolor=WHITE,
                    content=ft.Column(
                        spacing=10, controls=[t_qty, busy, ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])]
                    ),
                )
                bs2 = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
                page.open(bs2)

                def close_bs2(_=None):
                    page.close(bs2)
                    page.update()

                def do_ok(_):
                    n = backend.safe_int(t_qty.value)
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
                        okb = backend.add_qty(recid_stock, n, nombre_prod, depo_name)
                        if not okb:
                            raise ValueError("No se pudo agregar stock.")
                        load_all()
                        render_list()
                        close_bs2()
                        close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Stock agregado."))
                        page.snack_bar.open = True
                        page.update()
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        busy.visible = False
                        ok.disabled = False
                        cancel.disabled = False
                        page.update()

                ok.on_click = do_ok
                cancel.on_click = close_bs2

            return _handler

        def do_descargar(recid_stock: str, depo_name: str):
            def _handler(_):
                t_qty = ft.TextField(
                    label="Cantidad a descargar",
                    width=220,
                    value="1",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    input_filter=ft.InputFilter(allow=True, regex_string=r"[-0-9]", replacement_string=""),
                )
                busy = ft.ProgressBar(visible=False, width=220)
                ok = ft.FilledButton("Descargar", icon=ft.Icons.REMOVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
                cancel = ft.OutlinedButton("Cancelar")

                inner = ft.Container(
                    padding=16,
                    bgcolor=WHITE,
                    content=ft.Column(
                        spacing=10, controls=[t_qty, busy, ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])]
                    ),
                )
                bs2 = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
                page.open(bs2)

                def close_bs2(_=None):
                    page.close(bs2)
                    page.update()

                def do_ok(_):
                    n = backend.safe_int(t_qty.value)
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
                        okb = backend.descargar(recid_stock, n, nombre_prod, depo_name)
                        if not okb:
                            raise ValueError("Stock insuficiente.")
                        load_all()
                        render_list()
                        close_bs2()
                        close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Descarga realizada."))
                        page.snack_bar.open = True
                        page.update()
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        busy.visible = False
                        ok.disabled = False
                        cancel.disabled = False
                        page.update()

                ok.on_click = do_ok
                cancel.on_click = close_bs2

            return _handler

        def do_move(recid_stock: str, origin_recid: str, origin_name: str):
            def _handler(_):
                dest_options = [
                    ft.dropdown.Option(
                        key=d["RecID"], text=f'{d.get("id_deposito","")} — {d.get("nombre_deposito","")}'
                    )
                    for d in backend.depositos
                    if d.get("RecID") != origin_recid
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
                        spacing=10, controls=[dd_dest, t_qty, busy, ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])]
                    ),
                )
                bs2 = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
                page.open(bs2)

                def close_bs2(_=None):
                    page.close(bs2)
                    page.update()

                def do_ok(_):
                    dest = (dd_dest.value or "").strip()
                    n = backend.safe_int(t_qty.value)
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
                        dest_d = backend.depo_by_recid.get(dest, {})
                        dest_name = dest_d.get("nombre_deposito", "") or "(depósito desconocido)"
                        okb = backend.move_add_row(recid_stock, dest, n, nombre_prod, origin_name, dest_name)
                        if not okb:
                            raise ValueError("No se pudo mover: verifique cantidad y depósitos.")
                        load_all()
                        render_list()
                        close_bs2()
                        close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Movimiento realizado (nueva fila creada)."))
                        page.snack_bar.open = True
                        page.update()
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        busy.visible = False
                        ok.disabled = False
                        cancel.disabled = False
                        page.update()

                ok.on_click = do_ok
                cancel.on_click = close_bs2

            return _handler

        # botones handlers
        def on_add(_=None):
            if not selected_row:
                page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un depósito."))
                page.snack_bar.open = True
                page.update()
                return
            r = selected_row
            depo = backend.depo_by_recid.get(r.get("ID_deposito", ""), {})
            depo_name = depo.get("nombre_deposito", "") or "(depósito desconocido)"
            do_add_qty(r.get("RecID", ""), depo_name)(_)

        def on_out(_=None):
            if not selected_row:
                page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un depósito."))
                page.snack_bar.open = True
                page.update()
                return
            r = selected_row
            depo = backend.depo_by_recid.get(r.get("ID_deposito", ""), {})
            depo_name = depo.get("nombre_deposito", "") or "(depósito desconocido)"
            do_descargar(r.get("RecID", ""), depo_name)(_)

        def on_move(_=None):
            if not selected_row:
                page.snack_bar = ft.SnackBar(ft.Text("Elegí depósito origen en la lista superior."))
                page.snack_bar.open = True
                page.update()
                return
            r = selected_row
            origin_recid = r.get("ID_deposito", "")
            origin_name = (backend.depo_by_recid.get(origin_recid, {}) or {}).get("nombre_deposito", "") or "(depósito desconocido)"
            do_move(r.get("RecID", ""), origin_recid, origin_name)(_)

        btn_add.on_click = on_add
        btn_out.on_click = on_out
        btn_move.on_click = on_move

    # ---------- Panel por DEPÓSITO (lista ITEMS de ese depósito) ----------
    def open_deposito_panel(depo_recid: str):
        rows_depo = backend.rows_for_deposito(depo_recid)

        depo = backend.depo_by_recid.get(depo_recid, {})
        nombre_depo = depo.get("nombre_deposito", "") or "(depósito desconocido)"
        id_depo = depo.get("id_deposito", "") or "-"

        selected_row: Dict | None = None
        list_col = ft.Column(spacing=8, expand=True)
        row_wrappers: List[ft.Container] = []

        def make_row_item(row: Dict):
            p = backend.prod_by_recid.get(row.get("ID_producto", ""), {})
            nombre_prod = p.get("nombre_producto", "") or "(producto desconocido)"
            codigo_prod = p.get("codigo_producto", "") or "-"
            qty = row.get("cantidad", "0") or "0"

            chip = ft.Container(
                bgcolor=ft.Colors.GREY_50,
                border_radius=8,
                padding=10,
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

        btn_add = ft.FilledButton(
            "Agregar", icon=ft.Icons.ADD, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True
        )
        btn_move = ft.FilledButton(
            "Mover", icon=ft.Icons.SWAP_HORIZ, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True
        )
        btn_out = ft.FilledButton(
            "Descargar", icon=ft.Icons.REMOVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True
        )

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
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_EVENLY, controls=[btn_add, btn_move, btn_out]
                    ),
                ],
            ),
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True, elevation=8)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs)
            page.update()

        def do_add_qty(recid_stock: str, depo_name: str):
            def _h(_):
                t_qty = ft.TextField(
                    label="Cantidad a agregar",
                    width=220,
                    value="1",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    input_filter=ft.InputFilter(allow=True, regex_string=r"[-0-9]", replacement_string=""),
                )
                busy = ft.ProgressBar(visible=False, width=220)
                ok = ft.FilledButton("Agregar", icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
                cancel = ft.OutlinedButton("Cancelar")
                inner = ft.Container(
                    padding=16,
                    bgcolor=WHITE,
                    content=ft.Column(
                        spacing=10, controls=[t_qty, busy, ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])]
                    ),
                )
                bs2 = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
                page.open(bs2)

                def close_bs2(_=None):
                    page.close(bs2)
                    page.update()

                def do_ok(_):
                    n = backend.safe_int(t_qty.value)
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
                        okb = backend.add_qty(recid_stock, n, "", depo_name)
                        if not okb:
                            raise ValueError("No se pudo agregar stock.")
                        load_all()
                        render_list()
                        close_bs2()
                        close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Stock agregado."))
                        page.snack_bar.open = True
                        page.update()
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        busy.visible = False
                        ok.disabled = False
                        cancel.disabled = False
                        page.update()

                ok.on_click = do_ok
                cancel.on_click = close_bs2

            return _h

        def do_descargar(recid_stock: str, depo_name: str):
            def _h(_):
                t_qty = ft.TextField(
                    label="Cantidad a descargar",
                    width=220,
                    value="1",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    input_filter=ft.InputFilter(allow=True, regex_string=r"[-0-9]", replacement_string=""),
                )
                busy = ft.ProgressBar(visible=False, width=220)
                ok = ft.FilledButton("Descargar", icon=ft.Icons.REMOVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
                cancel = ft.OutlinedButton("Cancelar")
                inner = ft.Container(
                    padding=16,
                    bgcolor=WHITE,
                    content=ft.Column(
                        spacing=10, controls=[t_qty, busy, ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])]
                    ),
                )
                bs2 = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
                page.open(bs2)

                def close_bs2(_=None):
                    page.close(bs2)
                    page.update()

                def do_ok(_):
                    n = backend.safe_int(t_qty.value)
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
                        okb = backend.descargar(recid_stock, n, "", depo_name)
                        if not okb:
                            raise ValueError("Stock insuficiente.")
                        load_all()
                        render_list()
                        close_bs2()
                        close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Descarga realizada."))
                        page.snack_bar.open = True
                        page.update()
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        busy.visible = False
                        ok.disabled = False
                        cancel.disabled = False
                        page.update()

                ok.on_click = do_ok
                cancel.on_click = close_bs2

            return _h

        def do_move(recid_stock: str, origin_recid: str, origin_name: str):
            def _h(_):
                dest_options = [
                    ft.dropdown.Option(
                        key=d["RecID"], text=f'{d.get("id_deposito","")} — {d.get("nombre_deposito","")}'
                    )
                    for d in backend.depositos
                    if d.get("RecID") != origin_recid
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
                        spacing=10, controls=[dd_dest, t_qty, busy, ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])]
                    ),
                )
                bs2 = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
                page.open(bs2)

                def close_bs2(_=None):
                    page.close(bs2)
                    page.update()

                def do_ok(_):
                    dest = (dd_dest.value or "").strip()
                    n = backend.safe_int(t_qty.value)
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
                        dest_d = backend.depo_by_recid.get(dest, {})
                        dest_name = dest_d.get("nombre_deposito", "") or "(depósito desconocido)"
                        okb = backend.move_add_row(recid_stock, dest, n, "", origin_name, dest_name)
                        if not okb:
                            raise ValueError("No se pudo mover: verifique cantidad y depósitos.")
                        load_all()
                        render_list()
                        close_bs2()
                        close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Movimiento realizado (nueva fila creada)."))
                        page.snack_bar.open = True
                        page.update()
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                        page.snack_bar.open = True
                        page.update()
                    finally:
                        busy.visible = False
                        ok.disabled = False
                        cancel.disabled = False
                        page.update()

                ok.on_click = do_ok
                cancel.on_click = close_bs2

            return _h

        def on_add(_=None):
            if not selected_row:
                page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un item de la lista."))
                page.snack_bar.open = True
                page.update()
                return
            r = selected_row
            do_add_qty(r.get("RecID", ""), nombre_depo)(_)

        def on_out(_=None):
            if not selected_row:
                page.snack_bar = ft.SnackBar(ft.Text("Primero seleccioná un item de la lista."))
                page.snack_bar.open = True
                page.update()
                return
            r = selected_row
            do_descargar(r.get("RecID", ""), nombre_depo)(_)

        def on_move(_=None):
            if not selected_row:
                page.snack_bar = ft.SnackBar(ft.Text("Elegí el item origen en la lista."))
                page.snack_bar.open = True
                page.update()
                return
            r = selected_row
            origin_recid = r.get("ID_deposito", "")
            do_move(recid_stock=r.get("RecID", ""), origin_recid=origin_recid, origin_name=nombre_depo)(_)

        btn_add.on_click = on_add
        btn_out.on_click = on_out
        btn_move.on_click = on_move

    # ---------- Agregar Stock (nuevo producto) ----------
    def open_add_stock_new(_=None):
        ya_en_stock = {r.get("ID_producto", "") for r in backend.stock_rows if r.get("ID_producto")}
        disponibles = [p for p in backend.productos if p.get("RecID") not in ya_en_stock]

        dd_item = ft.Dropdown(
            label="Item",
            width=420,
            options=[
                ft.dropdown.Option(
                    key=p["RecID"], text=f'{p.get("codigo_producto","")} — {p.get("nombre_producto","")}'
                )
                for p in disponibles
            ],
        )
        dd_depo = ft.Dropdown(
            label="Depósito",
            width=420,
            options=[
                ft.dropdown.Option(
                    key=d["RecID"], text=f'{d.get("id_deposito","")} — {d.get("nombre_deposito","")}'
                )
                for d in backend.depositos
            ],
        )
        t_qty = ft.TextField(
            label="Cantidad",
            width=200,
            value="1",
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"[-0-9]", replacement_string=""),
            helper_text="Solo valor igual o mayor a 1.",
            helper_style=ft.TextStyle(color=ft.Colors.GREY_600, size=11),
        )
        hint = ft.Text("", size=12, color=ft.Colors.GREY_700)
        if not disponibles:
            hint.value = "No hay Items disponibles: todos ya tienen una fila en stock."
        busy = ft.ProgressBar(visible=False, width=420)
        btn_ok = ft.FilledButton(
            "Agregar", icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=(len(disponibles) == 0)
        )
        btn_cancel = ft.OutlinedButton("Cancelar")

        content = ft.Container(
            padding=16,
            bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Agregar Stock (nuevo producto)", size=18, weight=ft.FontWeight.W_700),
                    dd_item,
                    dd_depo,
                    t_qty,
                    hint,
                    busy,
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
                ],
            ),
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs)
            page.update()

        def do_add(_):
            item_recid = (dd_item.value or "").strip()
            depo_recid = (dd_depo.value or "").strip()
            qty_int = backend.safe_int((t_qty.value or "0"))
            if not item_recid or not depo_recid or qty_int < 1:
                page.snack_bar = ft.SnackBar(ft.Text("Elegí Item (disponible), Depósito y cantidad válida (≥ 1)."))
                page.snack_bar.open = True
                page.update()
                return

            btn_ok.disabled = True
            btn_cancel.disabled = True
            busy.visible = True
            page.update()
            try:
                dname = (backend.depo_by_recid.get(depo_recid, {}) or {}).get("nombre_deposito", "") or "(depósito desconocido)"
                pname = (backend.prod_by_recid.get(item_recid, {}) or {}).get("nombre_producto", "") or "(producto desconocido)"

                recid = backend.add_new_stock(item_recid, depo_recid, qty_int, pname, dname)
                if not recid:
                    raise ValueError("No se pudo crear la fila de stock.")

                load_all()
                render_list()
                close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Stock agregado."))
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True
                page.update()
            finally:
                busy.visible = False
                btn_ok.disabled = False
                btn_cancel.disabled = False
                page.update()

        btn_ok.on_click = do_add
        btn_cancel.on_click = close_bs

    # -------- Layout general --------
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[ft.Text("Stock", size=22, weight=ft.FontWeight.W_700), status],
    )

    btn_add_new = ft.FilledButton(
        "Agregar Stock (nuevo producto)",
        icon=ft.Icons.ADD,
        style=ft.ButtonStyle(bgcolor=RED, color=WHITE),
    )
    btn_add_new.on_click = open_add_stock_new

    right_controls = ft.Row(spacing=8, controls=[toggle_holder, filter_btn], alignment=ft.MainAxisAlignment.END)
    action_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[btn_add_new, right_controls])

    # Holder que impone altura mínima (~8 filas)
    lv_holder = ft.Stack(
    expand=True,
    controls=[
        # Base “fantasma” que fuerza una altura mínima
        ft.Container(height=MIN_LIST_HEIGHT, bgcolor=ft.Colors.TRANSPARENT),
        # La lista real, expandida
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
            controls=[
                header,
                search,
                action_row,
                lv_holder,  # ← usar solo este
            ],
        ),
    )

    # -------- Carga inicial --------
    load_all()
    toggle_holder.content = _repaint_toggle()
    render_list()

    # === SUSCRIPCIONES ===
    if bus:
        bus.subscribe("productos_changed", lambda _data: (backend.refresh_products(), render_list()))
        bus.subscribe("depositos_changed", lambda _data: (backend.refresh_depositos(), render_list()))
        bus.subscribe("stock_changed", lambda _data: (backend.refresh_stock(), render_list()))

    return root
