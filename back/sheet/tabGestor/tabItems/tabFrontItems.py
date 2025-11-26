# ./back/sheet/tabGestor/tabItems/tabFrontItems.py
from __future__ import annotations
import asyncio
import os
import flet as ft

from .listaItems import crear_lista_items

PRIMARY = "#4B39EF"
WHITE = ft.Colors.WHITE
UPLOAD_DIR = os.path.abspath(os.getenv("FLET_UPLOAD_DIR") or "./uploads")


def build_items_tab(page: ft.Page, backend, bus=None) -> ft.Control:
    if getattr(backend, "attach_page", None) and getattr(backend, "page", None) is None:
        try:
            backend.attach_page(page)
        except Exception:
            pass

    # ----- helpers -----
    def _safe_refresh():
        if hasattr(backend, "refresh_all"):
            backend.refresh_all()
        elif hasattr(backend, "refresh_items"):
            backend.refresh_items()

    def _run_task(coro_or_func, *args):
        try:
            return page.run_task(coro_or_func, *args)
        except AttributeError:
            if asyncio.iscoroutine(coro_or_func):
                return asyncio.get_event_loop().create_task(coro_or_func)
            if asyncio.iscoroutinefunction(coro_or_func):
                return asyncio.get_event_loop().create_task(coro_or_func(*args))
            return coro_or_func(*args)

    def _set_upload_busy(preview: ft.Container, on: bool, err: str | None = None):
        if not isinstance(preview, ft.Container):
            return
        meta = preview.data or {}
        busy = meta.get("busy")
        err_lbl = meta.get("error_label")
        dis_list = meta.get("disable_on_busy") or []
        if err_lbl:
            if on:
                err_lbl.visible = False; err_lbl.value = ""
            elif err:
                err_lbl.visible = True; err_lbl.value = err
        if busy:
            busy.visible = on
        for c in dis_list:
            try: c.disabled = on
            except Exception: pass
        page.update()

    # ----- UI top -----
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)
    sort_mode = {"value": "name_asc"}

    def set_sort(sm: str):
        sort_mode["value"] = sm
        render_list()

    search = ft.TextField(
        hint_text="Buscar ítem…",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=PRIMARY,
        focused_border_color=PRIMARY,
        content_padding=10,
        on_change=lambda _: render_list(),
    )

    filter_btn = ft.PopupMenuButton(
        icon=ft.Icons.FILTER_LIST,
        tooltip="Ordenar",
        items=[
            ft.PopupMenuItem(text="Nombre A–Z", on_click=lambda _: set_sort("name_asc")),
            ft.PopupMenuItem(text="Nombre Z–A", on_click=lambda _: set_sort("name_desc")),
            ft.PopupMenuItem(text="Código A–Z", on_click=lambda _: set_sort("id_asc")),
            ft.PopupMenuItem(text="Código Z–A", on_click=lambda _: set_sort("id_desc")),
        ],
    )

    lv_holder = ft.Container()

    # ----- FilePicker global (EDIT imagen) -----
    pending_upload = {"recid": None, "preview": None, "upload_name": None}

    async def _do_backend_attach(local_path: str, recid: str, preview: ft.Container):
        try:
            res = await asyncio.to_thread(backend.upload_and_attach_image, recid, local_path)
            if not res or not res.get("ok"):
                raise RuntimeError((res or {}).get("error") or "fallo upload/attach")
            preview.data["recid_imagen"] = res["imagen_url"]
            from back.sheet.tabGestor.imagen_asinc import renderizar_imagen_asinc
            renderizar_imagen_asinc(preview)
            _safe_refresh(); render_list()
            page.snack_bar = ft.SnackBar(ft.Text("Imagen actualizada.")); page.snack_bar.open = True; page.update()
        except Exception as ex:
            _set_upload_busy(preview, False, f"Error subiendo imagen: {ex}")
            page.snack_bar = ft.SnackBar(ft.Text(f"Error subiendo imagen: {ex}")); page.snack_bar.open = True; page.update()

    def _on_pick_result(e: ft.FilePickerResultEvent):
        if not e.files:
            prev = pending_upload.get("preview")
            if prev: _set_upload_busy(prev, False)
            page.snack_bar = ft.SnackBar(ft.Text("Selección cancelada.")); page.snack_bar.open = True; page.update(); return
        f = e.files[0]
        recid  = pending_upload["recid"]
        preview = pending_upload["preview"]
        if not (recid and preview):
            page.snack_bar = ft.SnackBar(ft.Text("Error interno: faltan referencias.")); page.snack_bar.open = True; page.update(); return
        if f.path:  # Desktop
            _run_task(_do_backend_attach, f.path, recid, preview); return
        pending_upload["upload_name"] = f.name
        upload_url = page.get_upload_url(f.name, 600)
        file_picker.upload([ft.FilePickerUploadFile(name=f.name, upload_url=upload_url)])

    def _on_upload(e: ft.FilePickerUploadEvent):
        recid  = pending_upload["recid"]
        preview = pending_upload["preview"]
        if not (recid and preview):
            return

        async def _wait_and_attach(local_path: str):
            for _ in range(40):
                if os.path.isfile(local_path): break
                await asyncio.sleep(0.05)
            if not os.path.isfile(local_path):
                _set_upload_busy(preview, False, f"No se encontró el archivo subido: {local_path}")
                page.snack_bar = ft.SnackBar(ft.Text(f"No se encontró el archivo subido: {local_path}")); page.snack_bar.open = True; page.update(); return
            _run_task(_do_backend_attach, local_path, recid, preview)

        if hasattr(e, "files") and e.files:  # estilo nuevo
            for uf in e.files:
                err = getattr(uf, "error", None)
                if err:
                    _set_upload_busy(preview, False, f"Error de subida: {err}")
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error de subida: {err}")); page.snack_bar.open = True; page.update()
                    continue
                done = False
                try:
                    done = getattr(uf, "status", None) == ft.FilePickerUploadStatus.COMPLETED
                except Exception:
                    pass
                if not done and getattr(uf, "progress", None) is not None:
                    done = uf.progress >= 1
                if not done:
                    continue
                local_path = getattr(uf, "path", None) or os.path.join(UPLOAD_DIR, getattr(uf, "name", None) or pending_upload.get("upload_name") or "")
                _run_task(_wait_and_attach, local_path)
            return

        # estilo viejo
        fname = getattr(e, "file_name", None) or getattr(e, "filename", None) or pending_upload.get("upload_name")
        if getattr(e, "error", None):
            _set_upload_busy(preview, False, f"Error de subida: {e.error}")
            page.snack_bar = ft.SnackBar(ft.Text(f"Error de subida: {e.error}")); page.snack_bar.open = True; page.update(); return
        if getattr(e, "progress", None) is not None and e.progress < 1:
            return
        local_path = os.path.join(UPLOAD_DIR, fname or "")
        _run_task(_wait_and_attach, local_path)

    file_picker = ft.FilePicker(on_result=_on_pick_result, on_upload=_on_upload)
    page.overlay.append(file_picker); page.update()

    # ----- render list -----
    def render_list():
        from back.sheet.tabGestor.imagen_asinc import ensure_image_for_container_async
        search_value = (search.value or "").strip()
        sort_value = sort_mode["value"]
        new_lv_holder, new_status = crear_lista_items(backend, search_value, sort_value, open_edit_panel)
        lv_holder.content = new_lv_holder.content
        lv_holder.height  = new_lv_holder.height
        status.value = new_status.value
        page.update()

        async def _render_images_async():
            await asyncio.sleep(0)
            conts = getattr(lv_holder.content, "controls", []) or []
            for c in conts:
                try: _run_task(ensure_image_for_container_async, c)
                except Exception: pass
            await asyncio.sleep(0.05); page.update()
        _run_task(_render_images_async)

    # ----- panel agregar -----
    def open_add_panel(_=None):
        from uuid import uuid4
        from back.sheet.tabGestor.imagen_asinc import renderizar_imagen_asinc

        PANEL_W = 560
        PREVIEW_W, PREVIEW_H = 300, 220
        PREVIEW_PH = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )

        uploaded = {"file_id": None, "view_link": None, "recid_img": None}
        committed = {"image_committed": False}

        big_img = ft.Image(src=PREVIEW_PH, width=PREVIEW_W, height=PREVIEW_H, fit=ft.ImageFit.COVER,
                           error_content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=24, color=ft.Colors.GREY_600))
        preview = ft.Container(content=big_img, border_radius=12, bgcolor=ft.Colors.WHITE,
                               alignment=ft.alignment.center, data={"recid_imagen": "", "img_control": big_img})
        load_bar = ft.ProgressBar(width=PREVIEW_W, visible=False)
        load_msg = ft.Text("", size=11, color=ft.Colors.GREY_700, visible=False)

        t_cod = ft.TextField(label="Código")
        t_nom = ft.TextField(label="Nombre")
        t_des = ft.TextField(label="Descripción")
        for tf in (t_cod, t_nom, t_des):
            tf.expand = True

        ok     = ft.FilledButton("Guardar", icon=ft.Icons.SAVE, style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE))
        cancel = ft.OutlinedButton("Cancelar")
        btn_upload = ft.FilledTonalButton("Cargar imagen", icon=ft.Icons.IMAGE_OUTLINED)
        btn_clear  = ft.OutlinedButton("Quitar imagen", icon=ft.Icons.DELETE_OUTLINE, disabled=True)

        def _set_img_busy(on: bool, msg: str = ""):
            load_bar.visible = on
            load_msg.visible = bool(msg)
            load_msg.value = msg
            for c in (btn_upload, btn_clear, ok, cancel, t_cod, t_nom, t_des):
                try: c.disabled = on
                except Exception: pass
            page.update()

        scrim_msg = ft.Text("", color=ft.Colors.WHITE)
        scrim = ft.Container(visible=False, expand=True, bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                             content=ft.Column(alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                               controls=[ft.ProgressRing(), ft.Container(height=8), scrim_msg]))

        def _lock_panel(lock: bool, msg: str = ""):
            scrim.visible = lock; scrim_msg.value = msg
            for c in (t_cod, t_nom, t_des, ok, cancel, btn_upload, btn_clear):
                try: c.disabled = lock
                except Exception: pass
            page.update()

        pending_name = {"value": None}

        def _make_uploader():
            from back.integrations.drive_user_uploader import DriveUserUploader
            from back.integrations.drive_user_uploader import DEFAULT_SCOPES  # noqa
            try:
                return DriveUserUploader.from_page(page)
            except Exception as e:
                # Fallback con token crudo si existiera
                tok = getattr(getattr(page, "auth", None), "token", None)
                if not isinstance(tok, dict) or not tok.get("access_token"):
                    raise e
                from google.oauth2.credentials import Credentials
                creds = Credentials(token=tok.get("access_token"), refresh_token=tok.get("refresh_token"),
                                    token_uri="https://oauth2.googleapis.com/token",
                                    client_id=os.getenv("GOOGLE_CLIENT_ID"), client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                                    scopes=tok.get("scopes"))
                from back.integrations.drive_user_uploader import DriveUserUploader as _U
                return _U(credentials=creds)

        def _cleanup_drive_file():
            try:
                fid = uploaded.get("file_id")
                if fid and not committed["image_committed"]:
                    try:
                        _make_uploader().delete_file(fid)
                    except Exception:
                        pass
            finally:
                uploaded.update({"file_id": None, "view_link": None, "recid_img": None})

        fp = ft.FilePicker()
        page.overlay.append(fp); page.update()

        def _on_pick_result(e: ft.FilePickerResultEvent):
            if not e.files:
                _set_img_busy(False); return
            f = e.files[0]
            if f.path:
                page.run_task(_upload_only, f.path); return
            pending_name["value"] = f.name
            upload_url = page.get_upload_url(f.name, 600)
            fp.upload([ft.FilePickerUploadFile(name=f.name, upload_url=upload_url)])

        def _on_upload(e: ft.FilePickerUploadEvent):
            if hasattr(e, "files") and e.files:
                for uf in e.files:
                    if getattr(uf, "error", None):
                        _set_img_busy(False); return
                    done = getattr(uf, "status", None) == ft.FilePickerUploadStatus.COMPLETED or (getattr(uf, "progress", 0) >= 1)
                    if not done: continue
                    local_path = getattr(uf, "path", None) or os.path.join(UPLOAD_DIR, getattr(uf, "name", None) or pending_name["value"] or "")
                    page.run_task(_upload_only, local_path)
                return
            if getattr(e, "error", None):
                _set_img_busy(False); return
            if getattr(e, "progress", None) is not None and e.progress < 1:
                return
            fname = getattr(e, "file_name", None) or getattr(e, "filename", None) or (pending_name["value"] or "")
            local_path = os.path.join(UPLOAD_DIR, fname)
            page.run_task(_upload_only, local_path)

        fp.on_result = _on_pick_result
        fp.on_upload = _on_upload

        async def _upload_only(local_path: str):
            _set_img_busy(True, "Subiendo imagen…")
            try:
                up = _make_uploader()
                file_id, view_link = await asyncio.to_thread(up.upload_to_path, local_path, "TacticaGestorSheet/ImagenGestor", True)
            except Exception as e:
                _set_img_busy(False)
                page.snack_bar = ft.SnackBar(ft.Text(f"No se puede subir a Drive: {e}")); page.snack_bar.open = True; page.update(); return
            uploaded.update({"file_id": file_id, "view_link": view_link})
            from uuid import uuid4
            uploaded["recid_img"] = uuid4().hex[:10]
            try:
                preview.data["recid_imagen"] = view_link
                renderizar_imagen_asinc(preview)
            except Exception:
                pass
            _set_img_busy(False)
            btn_clear.disabled = False; page.update()

        def _do_upload(_):
            _set_img_busy(True, "Subiendo imagen…")
            fp.pick_files(allow_multiple=False, allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"])

        def _do_clear(_):
            _cleanup_drive_file()
            preview.data["recid_imagen"] = ""
            big_img.src = PREVIEW_PH
            page.update(); btn_clear.disabled = True

        btn_upload.on_click = _do_upload
        btn_clear.on_click  = _do_clear

        scrim_container = ft.Container(visible=False)

        ok.on_click = lambda _ : do_ok()
        cancel.on_click = lambda _ : close_bs()

        def close_bs():
            _cleanup_drive_file()
            try: page.close(bs)
            except Exception: pass
            page.update()

        def do_ok():
            codigo = (t_cod.value or "").strip()
            nombre = (t_nom.value or "").strip()
            if not codigo or not nombre:
                page.snack_bar = ft.SnackBar(ft.Text("Código y Nombre son obligatorios.")); page.snack_bar.open = True; page.update(); return

            async def _save():
                try:
                    _lock_panel(True, "Guardando…")
                    recid_item = backend.add(codigo_producto=codigo, nombre_producto=nombre, descripcion_producto=(t_des.value or "").strip())
                    if not recid_item:
                        raise ValueError("No se pudo crear el ítem.")
                    if uploaded["view_link"] and uploaded["recid_img"]:
                        ok_img = backend.api_img.add(uploaded["recid_img"], uploaded["view_link"]) if getattr(backend, "api_img", None) else False
                        ok_itm = backend.api.update_by_recid(recid_item, RecID_imagen=uploaded["recid_img"]) if getattr(backend, "api", None) else False
                        if not (ok_img and ok_itm):
                            raise RuntimeError("No se pudo asociar la imagen al ítem.")
                    _safe_refresh(); render_list(); close_bs()
                    page.snack_bar = ft.SnackBar(ft.Text("Ítem agregado.")); page.snack_bar.open = True; page.update()
                except Exception as ex:
                    _lock_panel(False)
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}")); page.snack_bar.open = True; page.update()
            page.run_task(_save)

        inner = ft.Container(
            width=PANEL_W,
            padding=16,
            bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Agregar ítem", size=16, weight=ft.FontWeight.W_700),
                    ft.Row(spacing=8, controls=[btn_upload, btn_clear]),
                    preview, load_bar, load_msg,
                    ft.Column(spacing=6, controls=[t_cod, t_nom, t_des]),
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok]),
                ],
            ),
        )
        panel_stack = ft.Stack(controls=[inner, scrim])
        bs = ft.BottomSheet(content=ft.Container(alignment=ft.alignment.center, content=panel_stack), show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

    # ----- panel editar -----
    def open_edit_panel(row_key: str):
        from back.sheet.tabGestor.imagen_asinc import renderizar_imagen_asinc
        from back.sheet.tabGestor.imagen_storage import delete_local_image_by_link

        d = backend.item_by_recid.get(row_key)
        if not d:
            for r in (backend.items or []):
                if r.get("RecID") == row_key or r.get("codigo_producto") == row_key:
                    d = r; break
        if not d:
            page.snack_bar = ft.SnackBar(ft.Text(f"No se encontró el ítem ({row_key}).")); page.snack_bar.open = True; page.update(); return

        recid_real = (d.get("RecID") or "").strip()
        if not recid_real:
            page.snack_bar = ft.SnackBar(ft.Text("Registro sin RecID válido.")); page.snack_bar.open = True; page.update(); return

        PREVIEW_W, PREVIEW_H = 300, 240
        PANEL_W = 480
        PREVIEW_PH = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )

        link_actual = (d.get("imagen_url") or "").strip()
        recid_imagen_val = (link_actual or d.get("RecID_imagen") or "").strip()

        big_img = ft.Image(src=PREVIEW_PH, width=PREVIEW_W, height=PREVIEW_H, fit=ft.ImageFit.COVER,
                           error_content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=24, color=ft.Colors.GREY_600))

        ov_ref = ft.Ref[ft.Container]()
        def _show_overlay(e):
            if ov_ref.current is None: return
            ov_ref.current.opacity = 1.0 if e.data == "true" else 0.0
            ov_ref.current.update()

        def _do_delete_image(_=None):
            ok_sheet = backend.remove_image_for_item(recid_real)
            ok_file, tried, img_id = delete_local_image_by_link(link_actual)
            big_img.src = PREVIEW_PH; big_img.update()
            _safe_refresh(); render_list()
            page.snack_bar = ft.SnackBar(ft.Text("Imagen eliminada.")); page.snack_bar.open = True; page.update()

        edit_img_btn = ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Editar imagen", icon_size=16, height=28, width=28, style=ft.ButtonStyle(padding=0), icon_color=ft.Colors.GREY_400)
        del_img_btn  = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Eliminar imagen", icon_size=16, height=28, width=28, style=ft.ButtonStyle(padding=0), icon_color=ft.Colors.GREY_400, on_click=_do_delete_image)
        overlay_layer = ft.Container(ref=ov_ref, width=PREVIEW_W, height=PREVIEW_H, opacity=0, animate_opacity=200, alignment=ft.alignment.top_right, padding=6, bgcolor=None, content=ft.Row(spacing=6, alignment=ft.MainAxisAlignment.END, controls=[edit_img_btn, del_img_btn]))
        preview_stack = ft.Stack(width=PREVIEW_W, height=PREVIEW_H, controls=[big_img, overlay_layer])
        loading_bar = ft.ProgressBar(width=PREVIEW_W, visible=False)
        error_lbl   = ft.Text("", size=11, color=ft.Colors.RED_400, visible=False)

        preview = ft.Container(on_hover=_show_overlay, content=preview_stack, border_radius=12, padding=0, bgcolor=ft.Colors.WHITE,
                               data={"recid_imagen": recid_imagen_val, "img_control": big_img, "busy": loading_bar, "error_label": error_lbl})

        def _open_picker(_):
            pending_upload["recid"] = recid_real
            pending_upload["preview"] = preview
            _set_upload_busy(preview, True)
            file_picker.pick_files(allow_multiple=False, allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"])
        edit_img_btn.on_click = _open_picker

        t_cod = ft.TextField(label="Código", value=d.get("codigo_producto", ""))
        t_nom = ft.TextField(label="Nombre", value=d.get("nombre_producto", ""))
        t_des = ft.TextField(label="Descripción", value=d.get("descripcion_producto", ""))
        for tf in (t_cod, t_nom, t_des):
            tf.expand = True

        ok             = ft.FilledButton("Guardar", icon=ft.Icons.SAVE, style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE))
        btn_delete     = ft.FilledTonalButton("Eliminar", icon=ft.Icons.DELETE_OUTLINE)
        cancel         = ft.OutlinedButton("Cerrar")

        scrim_msg = ft.Text("", color=ft.Colors.WHITE)
        scrim = ft.Container(visible=False, expand=True, bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                             content=ft.Column(alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                               controls=[ft.ProgressRing(), ft.Container(height=8), scrim_msg]))
        delete_busy = ft.ProgressBar(visible=False)
        blockables = [t_cod, t_nom, t_des, ok, btn_delete, cancel, edit_img_btn, del_img_btn]

        def _lock_panel(lock: bool, msg: str = ""):
            scrim.visible = lock; scrim_msg.value = msg; delete_busy.visible = lock
            for c in blockables:
                try: c.disabled = lock
                except Exception: pass
            page.update()

        panel_col = ft.Column(
            spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Editar ítem", size=16, weight=ft.FontWeight.W_700),
                preview, loading_bar, error_lbl,
                ft.Column(spacing=12, controls=[
                    t_cod, t_nom, t_des,
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[btn_delete, ft.Row(controls=[cancel, ok])]),
                    delete_busy,
                ]),
            ],
        )
        panel_container = ft.Container(width=PANEL_W, padding=16, bgcolor=WHITE, content=panel_col)
        panel_stack = ft.Stack(controls=[panel_container, scrim])
        bs = ft.BottomSheet(content=ft.Container(alignment=ft.alignment.center, content=panel_stack), show_drag_handle=True, is_scroll_controlled=True)
        page.open(bs)

        async def _kick_preview():
            await asyncio.sleep(0)
            if recid_imagen_val:
                renderizar_imagen_asinc(preview)
        _run_task(_kick_preview)

        def close_bs(_=None):
            page.close(bs); page.update()

        def do_save(_):
            _lock_panel(True, "Guardando…")
            try:
                codigo = (t_cod.value or "").strip()
                nombre = (t_nom.value or "").strip()
                if not codigo or not nombre:
                    page.snack_bar = ft.SnackBar(ft.Text("Código y Nombre son obligatorios.")); page.snack_bar.open = True; page.update(); return
                okb = backend.update(recid_real, codigo_producto=codigo, nombre_producto=nombre, descripcion_producto=(t_des.value or "").strip())
                if not okb:
                    raise ValueError("No se pudo guardar.")
                _safe_refresh(); render_list(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Cambios guardados.")); page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}")); page.snack_bar.open = True; page.update()
            finally:
                _lock_panel(False)

        def _close_dlg(dlg):
            try: page.close(dlg)
            except Exception: dlg.open = False
            page.update()

        def _confirm_delete(dlg):
            _close_dlg(dlg)
            async def _do():
                try:
                    _lock_panel(True, "Eliminando…")
                    okb = await asyncio.to_thread(backend.delete, recid_real)
                    if not okb:
                        raise RuntimeError("No se pudo eliminar.")
                    try:
                        if hasattr(backend, "items") and isinstance(backend.items, list):
                            backend.items = [r for r in backend.items if (r.get("RecID") or "") != recid_real]
                        if hasattr(backend, "item_by_recid") and isinstance(backend.item_by_recid, dict):
                            backend.item_by_recid.pop(recid_real, None)
                    except Exception:
                        pass
                    _safe_refresh(); render_list(); page.close(bs)
                    page.snack_bar = ft.SnackBar(ft.Text("Ítem eliminado.")); page.snack_bar.open = True; page.update()
                finally:
                    _lock_panel(False)
            _run_task(_do)

        def _on_btn_delete_click(e):
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirmar eliminación"),
                content=ft.Text("¿Eliminar este ítem? Esta acción no se puede deshacer."),
                actions=[ft.TextButton("Cancelar", on_click=lambda __: (_close_dlg(dlg))), ft.TextButton("Eliminar", on_click=lambda __: (_confirm_delete(dlg)))],
            )
            page.open(dlg)

        ok.on_click = do_save
        btn_delete.on_click = _on_btn_delete_click
        cancel.on_click = close_bs

    # ----- layout principal -----
    header = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Text("Ítems", size=22, weight=ft.FontWeight.W_700), status])
    btn_add = ft.FilledButton("Agregar ítem", icon=ft.Icons.ADD, style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE), on_click=open_add_panel)
    right_controls = ft.Row(alignment=ft.MainAxisAlignment.END, controls=[filter_btn])
    action_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[btn_add, right_controls])

    root = ft.Container(
        bgcolor=ft.Colors.GREY_50,
        expand=True,
        border_radius=12,
        padding=16,
        content=ft.Column(spacing=10, expand=True, controls=[header, search, action_row, ft.Container(expand=True, content=lv_holder)]),
    )

    _safe_refresh(); render_list()
    if bus:
        try: bus.subscribe("items_changed", lambda _=None: (_safe_refresh(), render_list()))
        except Exception: pass

    return root