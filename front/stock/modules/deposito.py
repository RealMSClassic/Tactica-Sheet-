# front/stock/modules/deposito.py
import flet as ft
from typing import Optional, Dict, List
from back.sheet.log_api import LogAPI

from back.sheet.deposito_api import DepositoAPI
from back.sheet.stock_api import StockAPI  # para mover/verificar stock

RED = "#E53935"
WHITE = ft.Colors.WHITE


def depositos_view(page: ft.Page) -> ft.Control:
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

    api = DepositoAPI(page, sheet_id)
    logger = LogAPI(page, sheet_id)  # ⬅️ logger para la hoja 'logs'

    search = ft.TextField(
        hint_text="Buscar por ID o nombre...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED,
        content_padding=10,
    )
    lv = ft.ListView(spacing=8, expand=True, auto_scroll=False)
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)

    # estado
    cache: List[Dict] = []
    filtered: List[Dict] = []
    selected: Optional[Dict] = None

    # para resaltar selección
    row_controls: Dict[str, ft.Container] = {}   # RecID -> outer container
    by_recid: Dict[str, Dict] = {}               # RecID -> item

    def _safe_int(v):
        try:
            return int(str(v).strip() or "0")
        except Exception:
            return 0

    def load_data():
        nonlocal cache, filtered, selected, row_controls, by_recid
        cache = api.list()
        filtered = list(cache)
        by_recid = {it["RecID"]: it for it in cache if it.get("RecID")}
        selected = None
        btn_edit.disabled = True
        btn_del.disabled = True
        render_list()

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

    def render_list():
        lv.controls.clear()
        row_controls.clear()
        q = (search.value or "").strip().lower()
        data = filtered
        if q:
            data = [
                it for it in filtered
                if q in (it.get("nombre_deposito", "") or "").lower()
                or q in (it.get("id_deposito", "") or "").lower()
            ]
        for it in data:
            lv.controls.append(_row(it))
        status.value = f"Depósitos: {len(cache)} | Mostrando: {len(data)}"
        page.update()

    def _row(it: dict) -> ft.Control:
        recid = it.get("RecID", "")
        card = ft.Container(
            bgcolor=WHITE,
            border_radius=10,
            padding=12,
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Text(it.get("nombre_deposito", ""), size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87),
                    ft.Text(f"ID: {it.get('id_deposito', '')}", size=12, color=ft.Colors.GREY_700),
                    ft.Text(it.get("direccion_deposito", ""), size=12, color=ft.Colors.GREY_600, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(it.get("descripcion_deposito", ""), size=12, color=ft.Colors.GREY_600, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
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
            if q in (it.get("nombre_deposito", "") or "").lower()
            or q in (it.get("id_deposito", "") or "").lower()
        ]
        selected = None
        btn_edit.disabled = True
        btn_del.disabled = True
        render_list()

    search.on_change = on_search_change

    # ---------- Add ----------
    def open_add_bs(_=None):
        t_id = ft.TextField(label="ID depósito", width=380, autofocus=True, filled=True, bgcolor=WHITE)
        t_nom = ft.TextField(label="Nombre", width=380, filled=True, bgcolor=WHITE)
        t_dir = ft.TextField(label="Dirección", width=380, filled=True, bgcolor=WHITE)
        t_desc = ft.TextField(label="Descripción", width=380, filled=True, bgcolor=WHITE, multiline=True, min_lines=2, max_lines=4)
        busy = ft.ProgressBar(visible=False, width=380)
        btn_ok = ft.FilledButton("Agregar", icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_cancel = ft.OutlinedButton("Cancelar")

        content = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(spacing=10, controls=[
                ft.Text("Agregar depósito", size=18, weight=ft.FontWeight.W_700),
                t_id, t_nom, t_dir, t_desc, busy,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok])
            ])
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True); page.open(bs)

        def close_bs(_=None): page.close(bs); page.update()

        def do_add(_):
            idv = (t_id.value or "").strip()
            nom = (t_nom.value or "").strip()
            if not idv or not nom:
                page.snack_bar = ft.SnackBar(ft.Text("Completá ID y Nombre.")); page.snack_bar.open = True; page.update(); return
            busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
            try:
                api.add(id_deposito=idv, nombre_deposito=nom,
                        direccion_deposito=(t_dir.value or "").strip(),
                        descripcion_deposito=(t_desc.value or "").strip())
                load_data(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Depósito agregado.")); page.snack_bar.open = True; page.update()
                # ===== LOG: Agregar =====
                try:
                    logger.append(f"Agrego deposito {nom}", include_user_name_in_action=True)
                except Exception as _ex:
                    print("[WARN][LOG add deposito] No se pudo registrar:", _ex)
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}")); page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()
        btn_ok.on_click = do_add; btn_cancel.on_click = close_bs

    # ---------- Edit ----------
    def open_edit_bs(_=None):
        if not selected: return
        recid = selected.get("RecID", "")
        t_id = ft.TextField(label="ID depósito", width=380, filled=True, bgcolor=WHITE, value=selected.get("id_deposito", "") or "")
        t_nom = ft.TextField(label="Nombre", width=380, filled=True, bgcolor=WHITE, value=selected.get("nombre_deposito", "") or "")
        t_dir = ft.TextField(label="Dirección", width=380, filled=True, bgcolor=WHITE, value=selected.get("direccion_deposito", "") or "")
        t_desc = ft.TextField(label="Descripción", width=380, filled=True, bgcolor=WHITE, multiline=True, min_lines=2, max_lines=4, value=selected.get("descripcion_deposito", "") or "")
        busy = ft.ProgressBar(visible=False, width=380)
        btn_ok = ft.FilledButton("Guardar", icon=ft.Icons.SAVE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_cancel = ft.OutlinedButton("Cancelar")

        # Valores viejos para el log
        old_id   = str(selected.get("id_deposito", "") or "")
        old_name = str(selected.get("nombre_deposito", "") or "")

        content = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(spacing=10, controls=[
                ft.Text("Editar depósito", size=18, weight=ft.FontWeight.W_700),
                t_id, t_nom, t_dir, t_desc, busy,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok])
            ])
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True); page.open(bs)
        def close_bs(_=None): page.close(bs); page.update()

        def do_edit(_):
            idv = (t_id.value or "").strip()
            nom = (t_nom.value or "").strip()
            dirv = (t_dir.value or "").strip()
            desc = (t_desc.value or "").strip()
            if not idv or not nom:
                page.snack_bar = ft.SnackBar(ft.Text("ID y Nombre no pueden estar vacíos.")); page.snack_bar.open = True; page.update(); return
            busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
            try:
                ok = api.update_by_recid(recid, id_deposito=idv, nombre_deposito=nom, direccion_deposito=dirv, descripcion_deposito=desc)
                if not ok: raise ValueError("No se pudo actualizar (verificá el RecID).")
                load_data(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Depósito actualizado.")); page.snack_bar.open = True; page.update()
                # ===== LOG: Editar =====
                try:
                    logger.append(
                        "Edito\n"
                        f"  ID deposito  de {old_id} a {idv}\n"
                        f"  Nombre  de {old_name} a {nom}",
                        include_user_name_in_action=True,
                    )
                except Exception as _ex:
                    print("[WARN][LOG edit deposito] No se pudo registrar:", _ex)
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}")); page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()
        btn_ok.on_click = do_edit; btn_cancel.on_click = close_bs

    # ---------- Delete (con reubicación de stock si corresponde) ----------
    def open_delete_bs(_=None):
        if not selected:
            return

        recid = selected.get("RecID", "")
        nom = selected.get("nombre_deposito", "") or ""
        idv = selected.get("id_deposito", "") or ""

        stock_api = StockAPI(page, sheet_id)
        rows = stock_api.list()
        qty_total = sum(_safe_int(r.get("cantidad", 0)) for r in rows if r.get("ID_deposito") == recid)

        otros = [d for d in cache if d.get("RecID") != recid]
        num_otros = len(otros)

        # Dropdown Motivo
        motivos_base = ["Cierre de depósito", "Unificación", "Reubicación", "Error de alta", "Otro"]
        dd_motivo = ft.Dropdown(
            label="Motivo",
            width=420,
            options=[ft.dropdown.Option(m) for m in motivos_base],
            value=motivos_base[0],
        )

        busy = ft.ProgressBar(visible=False, width=420)
        btn_ok = ft.FilledButton("Eliminar", icon=ft.Icons.DELETE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_cancel = ft.OutlinedButton("Cancelar")

        # helpers de movimiento
        def move_all_to(dest_recid: str):
            fresh = stock_api.list()
            for r in fresh:
                if r.get("ID_deposito") == recid:
                    n = _safe_int(r.get("cantidad", 0))
                    if n > 0:
                        stock_api.move_add_row(r.get("RecID", ""), dest_recid, n)

        def distribute_equally(dest_recids: List[str]):
            if not dest_recids:
                return
            m = len(dest_recids)
            fresh = stock_api.list()
            for r in fresh:
                if r.get("ID_deposito") == recid:
                    n = _safe_int(r.get("cantidad", 0))
                    if n <= 0:
                        continue
                    base = n // m
                    rem = n % m
                    for idx, drec in enumerate(dest_recids):
                        part = base + (1 if idx < rem else 0)
                        if part > 0:
                            stock_api.move_add_row(r.get("RecID", ""), drec, part)

        # UIs según escenario
        if qty_total <= 0:
            # Sin stock -> confirmación simple + motivo
            content = ft.Container(
                padding=16, bgcolor=WHITE,
                content=ft.Column(spacing=12, controls=[
                    ft.Text("Eliminar depósito", size=18, weight=ft.FontWeight.W_700),
                    ft.Text(f"¿Querés eliminar el depósito «{nom}» (ID: {idv})?", size=13),
                    dd_motivo,
                    busy,
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
                ])
            )
            bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True); page.open(bs)

            def close_bs(_=None): page.close(bs); page.update()

            def do_del(_):
                motivo_sel = (dd_motivo.value or "").strip()
                busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
                try:
                    ok = api.delete_by_recid(recid)
                    if not ok: raise ValueError("No se pudo eliminar (verificá el RecID).")
                    load_data(); close_bs()
                    page.snack_bar = ft.SnackBar(ft.Text("Depósito eliminado.")); page.snack_bar.open = True; page.update()
                    # ===== LOG: Eliminar con motivo =====
                    try:
                        logger.append(f"Elimino el deposito {nom} por el motivo de {motivo_sel}", include_user_name_in_action=True)
                    except Exception as _ex:
                        print("[WARN][LOG delete deposito] No se pudo registrar:", _ex)
                except Exception as ex:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}")); page.snack_bar.open = True; page.update()
                finally:
                    busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()

            btn_ok.on_click = do_del
            btn_cancel.on_click = close_bs

        else:
            # Con stock
            if num_otros == 0:
                # No hay dónde mover: bloquear
                content = ft.Container(
                    padding=16, bgcolor=WHITE,
                    content=ft.Column(spacing=12, controls=[
                        ft.Text("Eliminar depósito", size=18, weight=ft.FontWeight.W_700),
                        ft.Text(f"El depósito «{nom}» (ID: {idv}) tiene {qty_total} unidades en stock y no existen otros depósitos para moverlas.", size=13, color=ft.Colors.RED),
                        ft.Text("Vaciá el stock o crea otro depósito antes de eliminar.", size=12, color=ft.Colors.GREY_700),
                        ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel]),
                    ])
                )
                bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True); page.open(bs)
                btn_cancel.on_click = lambda _: (page.close(bs), page.update())
                return

            if num_otros == 1:
                # Exactamente 1 destino: se moverá automáticamente ahí
                dest = otros[0]
                dest_nom = dest.get("nombre_deposito", "") or ""
                dest_idv = dest.get("id_deposito", "") or ""
                content = ft.Container(
                    padding=16, bgcolor=WHITE,
                    content=ft.Column(spacing=12, controls=[
                        ft.Text("Eliminar depósito (con reubicación)", size=18, weight=ft.FontWeight.W_700),
                        ft.Text(f"Este depósito tiene {qty_total} unidades. Se moverán automáticamente a «{dest_nom}» (ID: {dest_idv}).", size=13),
                        dd_motivo,
                        busy,
                        ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
                    ])
                )
                bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True); page.open(bs)

                def close_bs(_=None): page.close(bs); page.update()

                def do_move_then_delete(_):
                    motivo_sel = (dd_motivo.value or "").strip()
                    busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
                    try:
                        move_all_to(dest.get("RecID", ""))
                        ok = api.delete_by_recid(recid)
                        if not ok: raise ValueError("No se pudo eliminar (verificá el RecID).")
                        load_data(); close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Stock reubicado y depósito eliminado.")); page.snack_bar.open = True; page.update()
                        # ===== LOG: Eliminar con motivo =====
                        try:
                            logger.append(f"Elimino el deposito {nom} por el motivo de {motivo_sel}", include_user_name_in_action=True)
                        except Exception as _ex:
                            print("[WARN][LOG delete deposito] No se pudo registrar:", _ex)
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}")); page.snack_bar.open = True; page.update()
                    finally:
                        busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()

                btn_ok.on_click = do_move_then_delete
                btn_cancel.on_click = close_bs

            else:
                # 3 o más destinos: elegir estrategia
                rg = ft.RadioGroup(
                    value="uno",
                    content=ft.Column(spacing=6, controls=[
                        ft.Radio(value="uno", label="Mover todo a un depósito específico"),
                        ft.Radio(value="todos", label="Dividir equitativamente entre todos los depósitos disponibles"),
                    ])
                )
                dd_dest = ft.Dropdown(
                    label="Depósito destino",
                    width=420,
                    options=[ft.dropdown.Option(key=d["RecID"], text=f'{d.get("id_deposito","")} — {d.get("nombre_deposito","")}') for d in otros],
                    visible=True,  # visible cuando rg.value == "uno"
                )

                def on_rg_change(_):
                    dd_dest.visible = (rg.value == "uno")
                    page.update()
                rg.on_change = on_rg_change

                content = ft.Container(
                    padding=16, bgcolor=WHITE,
                    content=ft.Column(spacing=12, controls=[
                        ft.Text("Eliminar depósito (con reubicación)", size=18, weight=ft.FontWeight.W_700),
                        ft.Text(f"Este depósito tiene {qty_total} unidades. Elegí cómo reubicarlas antes de eliminar:", size=13),
                        rg,
                        dd_dest,
                        dd_motivo,
                        busy,
                        ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
                    ])
                )
                bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True); page.open(bs)

                def close_bs(_=None): page.close(bs); page.update()

                def do_route_then_delete(_):
                    motivo_sel = (dd_motivo.value or "").strip()
                    if rg.value == "uno":
                        dest = (dd_dest.value or "").strip()
                        if not dest:
                            page.snack_bar = ft.SnackBar(ft.Text("Elegí el depósito destino.")); page.snack_bar.open = True; page.update(); return
                    busy.visible = True; btn_ok.disabled = True; btn_cancel.disabled = True; page.update()
                    try:
                        if rg.value == "uno":
                            move_all_to(dest)
                        else:
                            distribute_equally([d["RecID"] for d in otros])
                        ok = api.delete_by_recid(recid)
                        if not ok: raise ValueError("No se pudo eliminar (verificá el RecID).")
                        load_data(); close_bs()
                        page.snack_bar = ft.SnackBar(ft.Text("Stock reubicado y depósito eliminado.")); page.snack_bar.open = True; page.update()
                        # ===== LOG: Eliminar con motivo =====
                        try:
                            logger.append(f"Elimino el deposito {nom} por el motivo de {motivo_sel}", include_user_name_in_action=True)
                        except Exception as _ex:
                            print("[WARN][LOG delete deposito] No se pudo registrar:", _ex)
                    except Exception as ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}")); page.snack_bar.open = True; page.update()
                    finally:
                        busy.visible = False; btn_ok.disabled = False; btn_cancel.disabled = False; page.update()

                btn_ok.on_click = do_route_then_delete
                btn_cancel.on_click = close_bs

    # Layout
    btn_add = ft.FilledButton("Agregar", icon=ft.Icons.ADD, on_click=open_add_bs, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
    btn_edit = ft.FilledButton("Editar", icon=ft.Icons.EDIT, on_click=open_edit_bs, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)
    btn_del = ft.FilledButton("Eliminar", icon=ft.Icons.DELETE, on_click=open_delete_bs, style=ft.ButtonStyle(bgcolor=RED, color=WHITE), disabled=True)

    header = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Depósitos", size=22, weight=ft.FontWeight.W_700), status])
    footer = ft.Row(alignment=ft.MainAxisAlignment.SPACE_EVENLY, controls=[btn_add, btn_edit, btn_del])

    root = ft.Container(
        bgcolor=ft.Colors.GREY_50, expand=True, border_radius=12, padding=16,
        content=ft.Column(spacing=10, expand=True, controls=[header, search, ft.Container(expand=True, content=lv), footer]),
    )

    load_data()
    return root
