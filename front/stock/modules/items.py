# front/stock/modules/items.py
import flet as ft
from typing import Optional, Dict, List

from back.sheet.producto_api import ProductoAPI
from back.sheet.log_api import LogAPI

RED = "#E53935"
WHITE = ft.Colors.WHITE


def items_view(page: ft.Page) -> ft.Control:
    """
    Gestión de Items (productos) con logging:
      + Agregar  -> "Agrego Item {item}"
      + Editar   -> "Edito \n  Codigo Item  de {old_code} a {new_code}\n  Nombre  de {old_name} a {new_name}"
      + Eliminar -> "Elimino el Item {item}"
    El nombre del usuario se guarda en ID_usuario (y también se antepone en el texto).
    """
    sheet_id = (
        page.client_storage.get("active_sheet_id")
        or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
    )

    if not sheet_id:
        return ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=ft.Text("Elegí un Sheet para continuar", size=18, color=ft.Colors.RED),
        )

    api = ProductoAPI(page, sheet_id)
    logger = LogAPI(page, sheet_id)

    # -------- estado --------
    cache: List[Dict] = []
    filtered: List[Dict] = []
    by_recid: Dict[str, Dict] = {}
    selected: Optional[Dict] = None

    status = ft.Text("", size=12, color=ft.Colors.GREY_600)

    search = ft.TextField(
        hint_text="Buscar por código o nombre...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED,
        content_padding=10,
    )
    lv = ft.ListView(spacing=8, expand=True, auto_scroll=False)

    row_controls: Dict[str, ft.Container] = {}

    # -------- helpers --------
    def load_data():
        nonlocal cache, filtered, by_recid, selected
        cache = api.list()
        filtered = list(cache)
        by_recid = {it["RecID"]: it for it in cache if it.get("RecID")}
        selected = None
        btn_edit.disabled = True
        btn_del.disabled = True
        render_list()

    def render_list():
        lv.controls.clear()
        row_controls.clear()
        q = (search.value or "").strip().lower()
        data = filtered
        if q:
            data = [
                it for it in filtered
                if q in (it.get("codigo_producto", "") or "").lower()
                or q in (it.get("nombre_producto", "") or "").lower()
            ]
        for it in data:
            lv.controls.append(_row(it))
        status.value = f"Items: {len(cache)} | Mostrando: {len(data)}"
        page.update()

    def _select_row(recid: str):
        nonlocal selected
        selected = by_recid.get(recid)
        for c in row_controls.values():
            c.border = None
        if recid in row_controls:
            row_controls[recid].border = ft.border.all(2, ft.Colors.BLUE_300)
        btn_edit.disabled = False
        btn_del.disabled = False
        page.update()

    def _row(it: dict) -> ft.Control:
        recid = it.get("RecID", "")
        code = it.get("codigo_producto", "") or "-"
        name = it.get("nombre_producto", "") or ""
        desc = it.get("descripcion_producto", "") or ""

        card = ft.Container(
            bgcolor=WHITE,
            border_radius=10,
            padding=12,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(name, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87),
                            ft.Text(f"Código: {code}", size=12, color=ft.Colors.GREY_700),
                            ft.Text(desc, size=12, color=ft.Colors.GREY_600, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                ],
            ),
        )
        outer = ft.Container(content=card)
        outer.on_click = lambda _: _select_row(recid)
        row_controls[recid] = outer
        return outer

    def on_search_change(_):
        nonlocal filtered, selected
        q = (search.value or "").strip().lower()
        filtered = list(cache) if not q else [
            it for it in cache
            if q in (it.get("codigo_producto", "") or "").lower()
            or q in (it.get("nombre_producto", "") or "").lower()
        ]
        selected = None
        btn_edit.disabled = True
        btn_del.disabled = True
        render_list()

    search.on_change = on_search_change

    # -------- Agregar --------
    def open_add_bs(_=None):
        t_code = ft.TextField(label="Código", width=420, filled=True, bgcolor=WHITE, autofocus=True)
        t_name = ft.TextField(label="Nombre", width=420, filled=True, bgcolor=WHITE)
        t_desc = ft.TextField(label="Descripción", width=420, filled=True, bgcolor=WHITE, multiline=True, min_lines=2, max_lines=4)
        busy = ft.ProgressBar(visible=False, width=420)
        btn_ok = ft.FilledButton("Agregar", icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_cancel = ft.OutlinedButton("Cancelar")

        content = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(spacing=10, controls=[
                ft.Text("Agregar Item", size=18, weight=ft.FontWeight.W_700),
                t_code, t_name, t_desc, busy,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
            ])
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_add(_):
            code = (t_code.value or "").strip()
            name = (t_name.value or "").strip()
            desc = (t_desc.value or "").strip()
            if not code or not name:
                page.snack_bar = ft.SnackBar(ft.Text("Completá Código y Nombre."))
                page.snack_bar.open = True; page.update(); return

            busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
            try:
                api.add(codigo_producto=code, nombre_producto=name, descripcion_producto=desc)
                load_data(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Item agregado."))
                page.snack_bar.open = True; page.update()

                # LOG ✅
                try:
                    logger.append(f"Agrego Item {name}")
                except Exception as log_ex:
                    print("[WARN][LOG items add] No se pudo registrar log:", log_ex)

            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()

        btn_ok.on_click = do_add
        btn_cancel.on_click = close_bs

    # -------- Editar --------
    def open_edit_bs(_=None):
        if not selected:
            return
        recid = selected.get("RecID", "")
        old_code = selected.get("codigo_producto", "") or ""
        old_name = selected.get("nombre_producto", "") or ""
        old_desc = selected.get("descripcion_producto", "") or ""

        t_code = ft.TextField(label="Código", width=420, filled=True, bgcolor=WHITE, value=old_code)
        t_name = ft.TextField(label="Nombre", width=420, filled=True, bgcolor=WHITE, value=old_name)
        t_desc = ft.TextField(label="Descripción", width=420, filled=True, bgcolor=WHITE, multiline=True, min_lines=2, max_lines=4, value=old_desc)
        busy = ft.ProgressBar(visible=False, width=420)
        btn_ok = ft.FilledButton("Guardar", icon=ft.Icons.SAVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_cancel = ft.OutlinedButton("Cancelar")

        content = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(spacing=10, controls=[
                ft.Text("Editar Item", size=18, weight=ft.FontWeight.W_700),
                t_code, t_name, t_desc, busy,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
            ])
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_edit(_):
            new_code = (t_code.value or "").strip()
            new_name = (t_name.value or "").strip()
            new_desc = (t_desc.value or "").strip()
            if not new_code or not new_name:
                page.snack_bar = ft.SnackBar(ft.Text("Código y Nombre no pueden estar vacíos."))
                page.snack_bar.open = True; page.update(); return

            busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
            try:
                ok = api.update_by_recid(
                    recid,
                    codigo_producto=new_code,
                    nombre_producto=new_name,
                    descripcion_producto=new_desc,
                )
                if not ok:
                    raise ValueError("No se pudo actualizar (verificá el RecID).")

                load_data(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Item actualizado."))
                page.snack_bar.open = True; page.update()

                # LOG ✅
                try:
                    msg = (
                        "Edito \n"
                        f"  Codigo Item  de {old_code} a {new_code}\n"
                        f"  Nombre  de {old_name} a {new_name}"
                    )
                    logger.append(msg)
                except Exception as log_ex:
                    print("[WARN][LOG items edit] No se pudo registrar log:", log_ex)

            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()

        btn_ok.on_click = do_edit
        btn_cancel.on_click = close_bs

    # -------- Eliminar --------
    def open_delete_bs(_=None):
        if not selected:
            return
        recid = selected.get("RecID", "")
        name = selected.get("nombre_producto", "") or ""
        code = selected.get("codigo_producto", "") or ""

        txt = ft.Text(f"¿Eliminar el Item «{name}» (Código: {code})?", size=13)
        busy = ft.ProgressBar(visible=False, width=420)
        btn_ok = ft.FilledButton("Eliminar", icon=ft.Icons.DELETE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_cancel = ft.OutlinedButton("Cancelar")

        content = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(spacing=10, controls=[
                ft.Text("Eliminar Item", size=18, weight=ft.FontWeight.W_700),
                txt, busy,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
            ])
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_del(_):
            busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
            try:
                ok = api.delete_by_recid(recid)
                if not ok:
                    raise ValueError("No se pudo eliminar (verificá el RecID).")

                load_data(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Item eliminado."))
                page.snack_bar.open = True; page.update()

                # LOG ✅
                try:
                    logger.append(f"Elimino el Item {name}")
                except Exception as log_ex:
                    print("[WARN][LOG items delete] No se pudo registrar log:", log_ex)

            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()

        btn_ok.on_click = do_del
        btn_cancel.on_click = close_bs

    # -------- Layout --------
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[ft.Text("Items", size=22, weight=ft.FontWeight.W_700), status],
    )
    btn_add = ft.FilledButton("Agregar", icon=ft.Icons.ADD, on_click=open_add_bs, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
    btn_edit = ft.FilledButton("Editar", icon=ft.Icons.EDIT, on_click=open_edit_bs, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)
    btn_del = ft.FilledButton("Eliminar", icon=ft.Icons.DELETE, on_click=open_delete_bs, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)

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
                ft.Container(expand=True, content=lv),
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_EVENLY, controls=[btn_add, btn_edit, btn_del]),
            ],
        ),
    )

    load_data()
    return root
