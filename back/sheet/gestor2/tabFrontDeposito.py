# ./back/sheet/tabGestor/tabFrontDeposito.py
from __future__ import annotations
import flet as ft
from back.sheet.tabGestor.tabDeposito.listaDeposito import crear_lista_depositos

PRIMARY = "#4B39EF"
WHITE = ft.Colors.WHITE

def build_deposito_tab(page: ft.Page, backend, bus=None) -> ft.Control:
    # Import: función que resuelve y asigna la imagen en cada item
    from back.sheet.tabGestor.imagen_asinc import renderizar_imagen_asinc

    # Attach page al backend si hace falta
    if getattr(backend, "attach_page", None) and getattr(backend, "page", None) is None:
        try:
            backend.attach_page(page)
        except Exception:
            pass

    # Controles base
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)
    search = ft.TextField(
        hint_text="Buscar depósito...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=PRIMARY,
        focused_border_color=PRIMARY,
        content_padding=10,
        on_change=lambda _: render_list(),
    )

    sort_mode = {"value": "name_asc"}  # name_asc | name_desc | id_asc | id_desc
    def set_sort(sm: str):
        sort_mode["value"] = sm
        render_list()

    filter_btn = ft.PopupMenuButton(
        icon=ft.Icons.FILTER_LIST,
        tooltip="Ordenar",
        items=[
            ft.PopupMenuItem(text="Nombre A–Z", on_click=lambda _: set_sort("name_asc")),
            ft.PopupMenuItem(text="Nombre Z–A", on_click=lambda _: set_sort("name_desc")),
            ft.PopupMenuItem(text="ID A–Z",     on_click=lambda _: set_sort("id_asc")),
            ft.PopupMenuItem(text="ID Z–A",     on_click=lambda _: set_sort("id_desc")),
        ],
    )

    # Holder de la lista (se actualiza en render_list)
    lv_holder = ft.Container()

    def render_list():
        search_value = (search.value or "").strip()
        sort_value = sort_mode["value"]
        new_lv_holder, new_status = crear_lista_depositos(
            backend, search_value, sort_value, open_edit_panel
        )
        lv_holder.content = new_lv_holder.content
        lv_holder.height = new_lv_holder.height
        status.value = new_status.value

        # Resolver imágenes reales en cada fila
        if hasattr(new_lv_holder.content, "controls"):
            for container in new_lv_holder.content.controls:
                try:
                    renderizar_imagen_asinc(container)
                except Exception as e:
                    print(f"[DepositoUI] Error renderizando imagen: {e}")
        page.update()

    # Panel agregar
    def open_add_panel(_=None):
        t_id = ft.TextField(label="ID depósito", width=420)
        t_nom = ft.TextField(label="Nombre", width=420)
        t_dir = ft.TextField(label="Dirección", width=420)
        t_des = ft.TextField(label="Descripción", width=420)
        busy = ft.ProgressBar(visible=False, width=420)
        ok = ft.FilledButton("Agregar", icon=ft.Icons.CHECK,
                             style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE))
        cancel = ft.OutlinedButton("Cancelar")

        inner = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[t_id, t_nom, t_dir, t_des, busy,
                          ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])],
            ),
        )
        bs = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_ok(_):
            iddep = (t_id.value or "").strip()
            nombre = (t_nom.value or "").strip()
            if not iddep or not nombre:
                page.snack_bar = ft.SnackBar(ft.Text("ID y Nombre son obligatorios."))
                page.snack_bar.open = True; page.update(); return
            busy.visible = True; ok.disabled = True; cancel.disabled = True; page.update()
            try:
                recid = backend.add(
                    id_deposito=iddep,
                    nombre_deposito=nombre,
                    direccion_deposito=(t_dir.value or "").strip(),
                    descripcion_deposito=(t_des.value or "").strip(),
                    # Si querés permitir setear RecID_imagen al crear, agregá un campo y pasalo aquí.
                )
                if not recid:
                    raise ValueError("No se pudo crear el depósito.")
                _safe_refresh(); render_list(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Depósito agregado."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False; ok.disabled = False; cancel.disabled = False; page.update()

        ok.on_click = do_ok
        cancel.on_click = close_bs

    # Panel editar
    def open_edit_panel(recid: str):
        d = backend.depo_by_recid.get(recid, {})
        t_id  = ft.TextField(label="ID depósito", width=420, value=d.get("id_deposito", ""))
        t_nom = ft.TextField(label="Nombre", width=420, value=d.get("nombre_deposito", ""))
        t_dir = ft.TextField(label="Dirección", width=420, value=d.get("direccion_deposito", ""))
        t_des = ft.TextField(label="Descripción", width=420, value=d.get("descripcion_deposito", ""))
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
                    ft.Text("Editar depósito", size=16, weight=ft.FontWeight.W_700),
                    t_id, t_nom, t_dir, t_des, busy,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[btn_del, ft.Row(controls=[cancel, ok])],
                    ),
                ],
            ),
        )
        bs = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_save(_):
            iddep = (t_id.value or "").strip()
            nombre = (t_nom.value or "").strip()
            if not iddep or not nombre:
                page.snack_bar = ft.SnackBar(ft.Text("ID y Nombre son obligatorios."))
                page.snack_bar.open = True; page.update(); return
            busy.visible = True; ok.disabled = True; cancel.disabled = True; btn_del.disabled = True; page.update()
            try:
                okb = backend.update(
                    recid,
                    id_deposito=iddep,
                    nombre_deposito=nombre,
                    direccion_deposito=(t_dir.value or "").strip(),
                    descripcion_deposito=(t_des.value or "").strip(),
                    # Si querés, también: RecID_imagen=...
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
                content=ft.Text("¿Eliminar este depósito? Esta acción no se puede deshacer."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda __: (_close_dlg(dlg))),
                    ft.TextButton("Eliminar", on_click=lambda __: (_confirm_delete(dlg))),
                ],
            )
            page.dialog = dlg
            dlg.open = True
            page.update()

        def _close_dlg(dlg):
            dlg.open = False
            page.update()

        def _confirm_delete(dlg):
            _close_dlg(dlg)
            try:
                okb = backend.delete(recid)
                if not okb:
                    raise ValueError("No se pudo eliminar.")
                _safe_refresh(); render_list()
                page.snack_bar = ft.SnackBar(ft.Text("Depósito eliminado."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()

        ok.on_click = do_save
        btn_del.on_click = do_delete
        cancel.on_click = close_bs

    # Refresh defensivo
    def _safe_refresh():
        if hasattr(backend, "refresh_all"):
            backend.refresh_all()
        elif hasattr(backend, "refresh_depositos"):
            backend.refresh_depositos()

    header = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    btn_add = ft.FilledButton(
        "Agregar depósito", icon=ft.Icons.ADD,
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
                status,
            ],
        ),
    )

    # Carga inicial
    print("[DepositoUI] backend:", type(backend), getattr(backend, "__module__", "?"), flush=True)
    _safe_refresh()
    render_list()

    # Suscripción opcional al bus
    if bus:
        try:
            bus.subscribe("depositos_changed", lambda _=None: (_safe_refresh(), render_list()))
        except Exception:
            pass

    return root
