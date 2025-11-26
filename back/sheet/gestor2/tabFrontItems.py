# ./back/sheet/gestor/tabFrontItems.py
from __future__ import annotations
import flet as ft
from typing import List, Tuple

__all__ = ["build_items_tab"]  # aseguro export

PRIMARY = "#4B39EF"
WHITE = ft.Colors.WHITE

ROW_HEIGHT = 96
ROW_SPACING = 8
MAX_ROWS_VISIBLE = 6

# --- Placeholder 1x1 para cuando la capa de imágenes no está disponible ---
_PLACEHOLDER_B64_1x1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)

def _is_web(page: ft.Page) -> bool:
    return getattr(page, "platform", "") == "web"

def _apply_placeholder(page: ft.Page, img: ft.Image, w: int, h: int, b64: str):
    if _is_web(page):
        img.src = f"data:image/png;base64,{b64}"
        img.src_base64 = None
    else:
        img.src_base64 = b64
        img.src = None
    img.width = w; img.height = h; img.fit = ft.ImageFit.COVER

def _guess_mime_from_b64(b64: str) -> str:
    import base64
    try:
        head = base64.b64decode(b64[:64], validate=False)
    except Exception:
        return "image/jpeg"
    if head.startswith(b"\xff\xd8"): return "image/jpeg"
    if head.startswith(b"\x89PNG"):  return "image/png"
    if head.startswith(b"GIF8"):     return "image/gif"
    if head[:4] == b"RIFF" and b"WEBP" in head[8:16]:
        return "image/webp"
    return "image/jpeg"

def _apply_b64(page: ft.Page, img: ft.Image, b64: str, w: int, h: int):
    if not b64:
        _apply_placeholder(page, img, w, h, _PLACEHOLDER_B64_1x1)
        return
    if _is_web(page):
        mime = _guess_mime_from_b64(b64)
        img.src = f"data:{mime};base64,{b64}"
        img.src_base64 = None
    else:
        img.src_base64 = b64
        img.src = None
    img.width = w; img.height = h; img.fit = ft.ImageFit.COVER

def _safe_update(ctrl: ft.Control):
    try:
        if getattr(ctrl, "page", None):
            ctrl.update()
    except Exception:
        pass

def _norm_img_recid(row: dict) -> str:
    return (row.get("RecID_imagen")
            or row.get("RecID_Imagen")
            or row.get("ID_Imagen")
            or "").strip()

def _lazy_img_layer():
    """
    Intenta importar coord de imágenes de modo perezoso para que
    el import del módulo NO falle si esa capa no existe.
    """
    try:
        from back.image.img_coord import get_img_coordinator, PLACEHOLDER_B64
        return get_img_coordinator, PLACEHOLDER_B64, None
    except Exception as e:
        # Solo deshabilito imágenes, pero el módulo exporta build_items_tab igual.
        print("[tabFrontItems] WARN: capa de imágenes deshabilitada:", repr(e), flush=True)
        return (None, _PLACEHOLDER_B64_1x1, e)

# =============================================================

def build_items_tab(page: ft.Page, backend, bus=None) -> ft.Control:
    """
    Lista y ABM de Ítems (hoja 'productos') con foto tipo “perfil”.
    - En la lista: imagen 64x64 (bordes 12).
    - Click en ítem: panel con imagen grande.
    - Imágenes cargan asíncronamente después de renderizar la lista.
    """
    # Import perezoso de la capa de imágenes
    _get_coord, PLACEHOLDER_B64, _img_err = _lazy_img_layer()
    coord = _get_coord() if _get_coord else None

    # Por si el backend se creó sin page y EXPONE attach_page
    if getattr(backend, "attach_page", None) and getattr(backend, "page", None) is None:
        try:
            backend.attach_page(page)
        except Exception:
            pass

    def _calc_height(n_rows: int) -> int:
        if n_rows <= 0:
            return ROW_HEIGHT
        vis = min(n_rows, MAX_ROWS_VISIBLE)
        return vis * ROW_HEIGHT + (vis - 1) * ROW_SPACING

    status = ft.Text("", size=12, color=ft.Colors.GREY_600)
    search = ft.TextField(
        hint_text="Buscar ítem (nombre, código, descripción)...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=PRIMARY,
        focused_border_color=PRIMARY,
        content_padding=10,
        on_change=lambda _: render_list(),
    )

    sort_mode = {"value": "name_asc"}  # name_asc | name_desc | code_asc | code_desc

    def set_sort(sm: str):
        sort_mode["value"] = sm
        render_list()

    filter_btn = ft.PopupMenuButton(
        icon=ft.Icons.FILTER_LIST,
        tooltip="Ordenar",
        items=[
            ft.PopupMenuItem(text="Nombre A–Z", on_click=lambda _: set_sort("name_asc")),
            ft.PopupMenuItem(text="Nombre Z–A", on_click=lambda _: set_sort("name_desc")),
            ft.PopupMenuItem(text="Código A–Z", on_click=lambda _: set_sort("code_asc")),
            ft.PopupMenuItem(text="Código Z–A", on_click=lambda _: set_sort("code_desc")),
        ],
    )

    lv = ft.ListView(spacing=ROW_SPACING, auto_scroll=False)
    lv_holder = ft.Container(height=_calc_height(0), content=lv)

    def render_list():
        lv.controls.clear()
        q = (search.value or "").strip()
        rows = backend.filter(q)

        sm = sort_mode["value"]
        def key_name(r): return (r.get("nombre_producto") or "").lower()
        def key_code(r): return (r.get("codigo_producto") or "").lower()

        if sm == "name_asc":
            rows = sorted(rows, key=key_name)
        elif sm == "name_desc":
            rows = sorted(rows, key=key_name, reverse=True)
        elif sm == "code_asc":
            rows = sorted(rows, key=key_code)
        elif sm == "code_desc":
            rows = sorted(rows, key=key_code, reverse=True)

        thumbs: List[Tuple[ft.Image, str]] = []
        get_id_nombre = getattr(backend, "get_id_nombre", None)

        for d in rows:
            rid_img = _norm_img_recid(d)
            id_nombre = get_id_nombre(rid_img) if (get_id_nombre and rid_img) else ""

            print("[ItemsUI.row]", {
                "RecID": d.get("RecID"),
                "codigo_producto": d.get("codigo_producto"),
                "nombre_producto": d.get("nombre_producto"),
                "descripcion_producto": d.get("descripcion_producto"),
                "RecID_imagen": rid_img,
            }, flush=True)
            print(f"[ItemsUI.row] imagen relacionada: RecID ({rid_img or '-'}) , Link ({id_nombre or '(sin link)'})",
                  flush=True)

            nombre = d.get("nombre_producto", "") or "(sin nombre)"
            codigo = d.get("codigo_producto", "") or "-"
            descripcion = d.get("descripcion_producto", "") or ""

            thumb_img = ft.Image()
            _apply_placeholder(page, thumb_img, 64, 64, PLACEHOLDER_B64)
            thumbs.append((thumb_img, rid_img))

            foto_box = ft.Container(
                width=64, height=64,
                bgcolor=ft.Colors.GREY_100,
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=thumb_img,
            )

            def on_click_row(_=None, recid=d.get("RecID", "")):
                open_edit_panel(recid)

            lv.controls.append(
                ft.Container(
                    on_click=on_click_row,
                    ink=True,
                    bgcolor=WHITE,
                    border_radius=10,
                    padding=12,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    foto_box,
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text(nombre, size=16, weight=ft.FontWeight.W_600,
                                                    color=ft.Colors.BLACK87),
                                            ft.Text(f"Código: {codigo}", size=12, color=ft.Colors.GREY_700),
                                            ft.Text(descripcion, size=12, color=ft.Colors.GREY_700, max_lines=2,
                                                    overflow=ft.TextOverflow.ELLIPSIS),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

        status.value = f"Ítems (productos): {len(rows)}"
        lv_holder.height = _calc_height(len(rows))
        page.update()

        # Carga async de imágenes SOLO si la capa está disponible
        if coord:
            async def kickoff_after_render():
                uniq = {rid for (_img, rid) in thumbs if rid}
                id_map = {}
                if get_id_nombre:
                    id_map = {rid: (get_id_nombre(rid) or "") for rid in uniq}
                else:
                    id_map = {rid: "" for rid in uniq}

                async def load_one(rid: str):
                    b64 = await coord.ensure_b64(rid, id_map.get(rid))
                    if not b64:
                        return
                    for img, rid2 in thumbs:
                        if rid2 == rid:
                            _apply_b64(page, img, b64, 64, 64)
                            _safe_update(img)

                import asyncio
                await asyncio.gather(*(load_one(r) for r in uniq))

            page.run_task(kickoff_after_render)

    def open_add_panel(_=None):
        t_code = ft.TextField(label="Código", width=420)
        t_nom = ft.TextField(label="Nombre", width=420)
        t_des = ft.TextField(label="Descripción", width=420)
        busy = ft.ProgressBar(visible=False, width=420)
        ok = ft.FilledButton("Agregar", icon=ft.Icons.CHECK,
                             style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE))
        cancel = ft.OutlinedButton("Cancelar")

        inner = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Agregar ítem (producto)", size=16, weight=ft.FontWeight.W_700),
                    t_code, t_nom, t_des, busy,
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok]),
                ],
            ),
        )
        bs = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_ok(_):
            code = (t_code.value or "").strip()
            nombre = (t_nom.value or "").strip()
            if not code or not nombre:
                page.snack_bar = ft.SnackBar(ft.Text("Código y Nombre son obligatorios."))
                page.snack_bar.open = True; page.update(); return
            busy.visible = True; ok.disabled = True; cancel.disabled = True; page.update()
            try:
                recid = backend.add(
                    codigo_producto=code,
                    nombre_producto=nombre,
                    descripcion_producto=(t_des.value or "").strip(),
                )
                if not recid:
                    raise ValueError("No se pudo crear el ítem (producto).")
                _safe_refresh(); render_list(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Ítem agregado."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; ok.disabled = False; cancel.disabled = False; page.update()

        ok.on_click = do_ok
        cancel.on_click = close_bs

    def open_edit_panel(recid: str):
        d = backend.item_by_recid.get(recid, {})
        rid_img = _norm_img_recid(d)

        get_id_nombre = getattr(backend, "get_id_nombre", None)
        id_nombre = get_id_nombre(rid_img) if (get_id_nombre and rid_img) else ""

        print("[ItemsUI.open_edit]", {
            "RecID": d.get("RecID"),
            "codigo_producto": d.get("codigo_producto"),
            "nombre_producto": d.get("nombre_producto"),
            "descripcion_producto": d.get("descripcion_producto"),
            "RecID_imagen": rid_img,
        }, flush=True)
        print(f"[ItemsUI.open_edit] imagen relacionada: RecID ({rid_img or '-'}) , Link ({id_nombre or '(sin link)'})",
              flush=True)

        t_code = ft.TextField(label="Código", width=420, value=d.get("codigo_producto", ""))
        t_nom = ft.TextField(label="Nombre", width=420, value=d.get("nombre_producto", ""))
        t_des = ft.TextField(label="Descripción", width=420, value=d.get("descripcion_producto", ""))

        big_img = ft.Image()
        _apply_placeholder(page, big_img, 440, 440, PLACEHOLDER_B64)
        big_box = ft.Container(
            width=460, height=460, bgcolor=ft.Colors.GREY_50, border_radius=12,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS, content=big_img,
        )

        busy = ft.ProgressBar(visible=False, width=420)
        ok = ft.FilledButton("Guardar", icon=ft.Icons.SAVE,
                             style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE))
        btn_del = ft.FilledTonalButton("Eliminar", icon=ft.Icons.DELETE_OUTLINE)
        cancel = ft.OutlinedButton("Cerrar")

        inner = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Editar ítem (producto)", size=16, weight=ft.FontWeight.W_700),
                    big_box,
                    t_code, t_nom, t_des, busy,
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                           controls=[btn_del, ft.Row(controls=[cancel, ok])]),
                ],
            ),
        )
        bs = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        # Cargar imagen grande solo si coord está disponible
        if coord and rid_img:
            async def _load_big():
                b64 = await coord.ensure_b64(rid_img, id_nombre)
                if b64:
                    _apply_b64(page, big_img, b64, 440, 440)
                    _safe_update(big_img)
            page.run_task(_load_big)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_save(_):
            code = (t_code.value or "").strip()
            nombre = (t_nom.value or "").strip()
            if not code or not nombre:
                page.snack_bar = ft.SnackBar(ft.Text("Código y Nombre son obligatorios."))
                page.snack_bar.open = True; page.update(); return
            busy.visible = True; ok.disabled = True; cancel.disabled = True; btn_del.disabled = True; page.update()
            try:
                okb = backend.update(
                    recid,
                    codigo_producto=code,
                    nombre_producto=nombre,
                    descripcion_producto=(t_des.value or "").strip(),
                )
                if not okb:
                    raise ValueError("No se pudo guardar.")
                _safe_refresh(); render_list(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Cambios guardados."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; ok.disabled = False; cancel.disabled = False; btn_del.disabled = False; page.update()

        def do_delete(_):
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirmar eliminación"),
                content=ft.Text("¿Eliminar este ítem (producto)? Esta acción no se puede deshacer."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda __: (_close_dlg(dlg))),
                    ft.TextButton("Eliminar", on_click=lambda __: (_confirm_delete(dlg))),
                ],
            )
            page.dialog = dlg
            dlg.open = True
            page.update()

        def _close_dlg(dlg):
            dlg.open = False; page.update()

        def _confirm_delete(dlg):
            _close_dlg(dlg)
            try:
                okb = backend.delete(recid)
                if not okb:
                    raise ValueError("No se pudo eliminar.")
                _safe_refresh(); render_list()
                page.snack_bar = ft.SnackBar(ft.Text("Ítem eliminado."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()

        ok.on_click = do_save
        btn_del.on_click = do_delete
        cancel.on_click = close_bs

    def _safe_refresh():
        if hasattr(backend, "refresh_all"):
            backend.refresh_all()
        elif hasattr(backend, "refresh_items"):
            backend.refresh_items()

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[ft.Text("Ítems (Productos)", size=22, weight=ft.FontWeight.W_700), status],
    )
    btn_add = ft.FilledButton(
        "Agregar ítem",
        icon=ft.Icons.ADD,
        style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE),
        on_click=open_add_panel,
    )
    right_controls = ft.Row(alignment=ft.MainAxisAlignment.END, controls=[filter_btn])
    action_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[btn_add, right_controls],
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
                ft.Container(expand=True, content=lv_holder),
            ],
        ),
    )

    print("[ItemsUI] backend:", type(backend), getattr(backend, "__module__", "?"), flush=True)
    _safe_refresh()
    render_list()

    if bus:
        try:
            bus.subscribe("productos_changed", lambda _=None: (_safe_refresh(), render_list()))
        except Exception:
            pass

    return root
