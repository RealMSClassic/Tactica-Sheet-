# ./back/sheet/tabGestor/tabFrontDeposito.py
from __future__ import annotations
import asyncio
import os
import flet as ft

from back.sheet.tabGestor.tabDeposito.listaDeposito import crear_lista_depositos

PRIMARY = "#4B39EF"
WHITE = ft.Colors.WHITE

# Carpeta local para subidas (modo web / server)
UPLOAD_DIR = os.path.abspath(os.getenv("FLET_UPLOAD_DIR") or "./uploads")


def build_deposito_tab(page: ft.Page, backend, bus=None) -> ft.Control:
    # Adjuntar page al backend si todavía no lo tiene
    if getattr(backend, "attach_page", None) and getattr(backend, "page", None) is None:
        try:
            backend.attach_page(page)
        except Exception:
            pass

    # ----------------- helpers -----------------
    def _has_valid_drive_oauth() -> bool:
        """Consideramos válido si podemos construir el uploader real."""
        try:
            from back.integrations.drive_user_uploader import DriveUserUploader
            DriveUserUploader.from_page(page)  # si falla, no hay sesión usable
            print("[OAUTH] OK: DriveUserUploader.from_page(page) construído.", flush=True)
            return True
        except Exception as e:
            print(f"[OAUTH] FAIL: {e}", flush=True)
            # Diagnóstico extra
            try:
                tok = getattr(getattr(page, "auth", None), "token", None)
                print(f"[OAUTH] page.auth.token type={type(tok)} keys={list(tok.keys()) if isinstance(tok, dict) else '-'}", flush=True)
            except Exception as ex2:
                print(f"[OAUTH] page.auth introspection error: {ex2}", flush=True)
            try:
                if hasattr(page, "client_storage"):
                    for k in ("google_oauth_token","google_creds","google_token","oauth_token","flet_oauth_token","drive_token"):
                        v = page.client_storage.get(k)
                        print(f"[OAUTH] client_storage[{k}] -> {type(v)} keys={list(v.keys()) if isinstance(v, dict) else '-'}", flush=True)
            except Exception as ex3:
                print(f"[OAUTH] client_storage introspection error: {ex3}", flush=True)
            return False

    def _safe_refresh():
        if hasattr(backend, "refresh_all"):
            backend.refresh_all()
        elif hasattr(backend, "refresh_depositos"):
            backend.refresh_depositos()

    def _run_task(coro_or_func, *args):
        """Ejecuta tareas async con page.run_task si está; si no, usa asyncio."""
        try:
            return page.run_task(coro_or_func, *args)
        except AttributeError:
            if asyncio.iscoroutine(coro_or_func):
                return asyncio.get_event_loop().create_task(coro_or_func)
            if asyncio.iscoroutinefunction(coro_or_func):
                return asyncio.get_event_loop().create_task(coro_or_func(*args))
            return coro_or_func(*args)

    def _set_upload_busy(preview: ft.Container, on: bool, err: str | None = None):
        """
        Enciende/apaga barra y deshabilita/habilita el formulario
        mientras sube/adjunta/renderiza la imagen (EDIT).
        """
        if not isinstance(preview, ft.Container):
            return
        meta = preview.data or {}
        busy = meta.get("busy")
        err_lbl = meta.get("error_label")
        dis_list = meta.get("disable_on_busy") or []
        if err_lbl:
            if on:
                err_lbl.visible = False
                err_lbl.value = ""
            elif err:
                err_lbl.visible = True
                err_lbl.value = err
        if busy:
            busy.visible = on
        for c in dis_list:
            try:
                c.disabled = on
            except Exception:
                pass
        page.update()

    # ----------------- UI top -----------------
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)
    sort_mode = {"value": "name_asc"}

    def set_sort(sm: str):
        sort_mode["value"] = sm
        render_list()

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

    # holder de la lista
    lv_holder = ft.Container()

    # ----------------- FilePicker global (para EDIT) -----------------
    pending_upload = {"recid": None, "preview": None, "upload_name": None}

    async def _do_backend_attach(local_path: str, recid: str, preview: ft.Container):
        """
        (EDIT) Sube a Drive + vincula en Sheets. Mantiene busy hasta que el preview renderiza.
        """
        try:
            print(f"[UPLOAD] start recid={recid} local_path={local_path}", flush=True)
            res = await asyncio.to_thread(backend.upload_and_attach_image, recid, local_path)
            print(f"[UPLOAD] result={res}", flush=True)
            if not res or not res.get("ok"):
                raise RuntimeError((res or {}).get("error") or "fallo upload/attach")

            new_link = res["imagen_url"]
            preview.data["recid_imagen"] = new_link

            # disparamos carga/decodificación del preview; imagen_asinc apagará el busy al terminar
            from back.sheet.tabGestor.imagen_asinc import renderizar_imagen_asinc
            renderizar_imagen_asinc(preview)

            # refrescar lista
            _safe_refresh()
            render_list()

            page.snack_bar = ft.SnackBar(ft.Text("Imagen actualizada."))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            # error: apagar busy y mostrar motivo
            _set_upload_busy(preview, False, f"Error subiendo imagen: {ex}")
            page.snack_bar = ft.SnackBar(ft.Text(f"Error subiendo imagen: {ex}"))
            page.snack_bar.open = True
            page.update()

    def _on_pick_result(e: ft.FilePickerResultEvent):
        """Desktop: usa path. Web: inicia upload() al servidor Flet."""
        if not e.files:
            print("[FP] cancelado", flush=True)
            prev = pending_upload.get("preview")
            if prev:
                _set_upload_busy(prev, False)  # quitar busy al cancelar
            page.snack_bar = ft.SnackBar(ft.Text("Selección cancelada."))
            page.snack_bar.open = True
            page.update()
            return

        f = e.files[0]
        print(
            f"[FP] name={f.name} size={getattr(f, 'size', '?')} mime={getattr(f, 'mime_type', '?')} path={f.path}",
            flush=True,
        )

        recid = pending_upload["recid"]
        preview = pending_upload["preview"]
        if not (recid and preview):
            print("[FP] faltan referencias (recid/preview)", flush=True)
            page.snack_bar = ft.SnackBar(ft.Text("Error interno: faltan referencias de edición."))
            page.snack_bar.open = True
            page.update()
            return

        # Desktop
        if f.path:
            _run_task(_do_backend_attach, f.path, recid, preview)
            return

        # Web
        print("[FP] path vacío (web) -> upload_url", flush=True)
        pending_upload["upload_name"] = f.name
        upload_url = page.get_upload_url(f.name, 600)
        file_picker.upload([ft.FilePickerUploadFile(name=f.name, upload_url=upload_url)])

    def _on_upload(e: ft.FilePickerUploadEvent):
        """Mantiene busy hasta terminar attach+preview (EDIT, modo web)."""
        recid = pending_upload["recid"]
        preview = pending_upload["preview"]
        if not (recid and preview):
            print("[UPLOAD] faltan referencias (recid/preview) en on_upload", flush=True)
            return

        async def _wait_and_attach(local_path: str):
            for _ in range(40):  # hasta 2s
                if os.path.isfile(local_path):
                    break
                await asyncio.sleep(0.05)
            if not os.path.isfile(local_path):
                _set_upload_busy(preview, False, f"No se encontró el archivo subido: {local_path}")
                page.snack_bar = ft.SnackBar(ft.Text(f"No se encontró el archivo subido: {local_path}"))
                page.snack_bar.open = True
                page.update()
                print(f"[UPLOAD] archivo no encontrado local_path={local_path}", flush=True)
                return
            _run_task(_do_backend_attach, local_path, recid, preview)

        # Estilo nuevo
        if hasattr(e, "files") and e.files:
            for uf in e.files:
                status = getattr(uf, "status", None)
                progress = getattr(uf, "progress", None)
                error = getattr(uf, "error", None)
                name = getattr(uf, "name", None)
                path = getattr(uf, "path", None)
                print(
                    f"[UPLOAD:new] name={name} status={status} progress={progress} error={error} path={path}",
                    flush=True,
                )

                done = False
                if status is not None:
                    try:
                        done = (status == ft.FilePickerUploadStatus.COMPLETED)
                    except Exception:
                        done = False
                if not done and progress is not None:
                    done = progress >= 1
                if error or not done:
                    if error:
                        _set_upload_busy(preview, False, f"Error de subida: {error}")
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error de subida: {error}"))
                        page.snack_bar.open = True
                        page.update()
                    continue

                local_path = path or os.path.join(UPLOAD_DIR, name or pending_upload.get("upload_name") or "")
                _run_task(_wait_and_attach, local_path)
            return

        # Estilo viejo
        fname = getattr(e, "file_name", None) or getattr(e, "filename", None) or pending_upload.get("upload_name")
        progress = getattr(e, "progress", None)
        error = getattr(e, "error", None)
        print(f"[UPLOAD:old] file_name={fname} progress={progress} error={error}", flush=True)
        if error:
            _set_upload_busy(preview, False, f"Error de subida: {error}")
            page.snack_bar = ft.SnackBar(ft.Text(f"Error de subida: {error}"))
            page.snack_bar.open = True
            page.update()
            return
        if progress is not None and progress < 1:
            return
        local_path = os.path.join(UPLOAD_DIR, fname or "")
        _run_task(_wait_and_attach, local_path)

    # Un FilePicker global para EDIT
    file_picker = ft.FilePicker(on_result=_on_pick_result, on_upload=_on_upload)
    page.overlay.append(file_picker)
    page.update()

    # ----------------- render de la lista -----------------
    def render_list():
        from back.sheet.tabGestor.imagen_asinc import ensure_image_for_container_async

        search_value = (search.value or "").strip()
        sort_value = sort_mode["value"]

        new_lv_holder, new_status = crear_lista_depositos(
            backend, search_value, sort_value, open_edit_panel
        )

        lv_holder.content = new_lv_holder.content
        lv_holder.height = new_lv_holder.height
        status.value = new_status.value
        page.update()

        async def _render_images_async():
            await asyncio.sleep(0)
            conts = getattr(lv_holder.content, "controls", []) or []
            for c in conts:
                try:
                    _run_task(ensure_image_for_container_async, c)
                except Exception as ex:
                    print(f"[IMG async] schedule error: {ex}", flush=True)
            await asyncio.sleep(0.05)
            page.update()

        _run_task(_render_images_async)

    # ----------------- panel agregar -----------------
    def open_add_panel(_=None):
        from uuid import uuid4
        from back.sheet.tabGestor.imagen_asinc import renderizar_imagen_asinc

        PANEL_W = 600
        PREVIEW_W, PREVIEW_H = 300, 220
        PREVIEW_PH = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )

        # Estado de imagen subida a Drive pero no comprometida aún en Sheets
        uploaded = {"file_id": None, "view_link": None, "recid_img": None}
        committed = {"image_committed": False}  # True solo cuando se grabó en Sheets

        # ======= UI: preview =======
        big_img = ft.Image(
            src=PREVIEW_PH, width=PREVIEW_W, height=PREVIEW_H, fit=ft.ImageFit.COVER,
            error_content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=24, color=ft.Colors.GREY_600),
        )
        preview = ft.Container(
            content=big_img,
            border_radius=12,
            bgcolor=ft.Colors.WHITE,
            alignment=ft.alignment.center,
            data={"recid_imagen": "", "img_control": big_img},
        )
        load_bar = ft.ProgressBar(width=PREVIEW_W, visible=False)
        load_msg = ft.Text("", size=11, color=ft.Colors.GREY_700, visible=False)
        drive_state_lbl = ft.Text(
            "Google Drive: conectado" if _has_valid_drive_oauth() else "Google Drive: no conectado",
            size=11, color=ft.Colors.GREY_600,
        )

        # ======= Form (campos, compactos) =======
        t_id  = ft.TextField(label="ID depósito")
        t_nom = ft.TextField(label="Nombre")
        t_dir = ft.TextField(label="Dirección")
        t_des = ft.TextField(label="Descripción")
        for tf in (t_id, t_nom, t_dir, t_des):
            tf.width = None
            tf.expand = True  # tamaño por defecto; sin tocar placeholder/hint size

        ok     = ft.FilledButton("Guardar", icon=ft.Icons.SAVE, style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE))
        cancel = ft.OutlinedButton("Cancelar")
        btn_upload = ft.FilledTonalButton("Cargar imagen", icon=ft.Icons.IMAGE_OUTLINED, disabled=not _has_valid_drive_oauth())
        btn_clear  = ft.OutlinedButton("Quitar imagen", icon=ft.Icons.DELETE_OUTLINE, disabled=True)

        # ===== Busy helpers =====
        def _set_img_busy(on: bool, msg: str = ""):
            load_bar.visible = on
            load_msg.visible = bool(msg)
            load_msg.value = msg
            # bloquear mientras sube
            for c in (btn_upload, btn_clear, ok, cancel, t_id, t_nom, t_dir, t_des):
                try:
                    c.disabled = on
                except Exception:
                    pass
            page.update()

        def _set_form_busy(on: bool):
            for c in (t_id, t_nom, t_dir, t_des, ok, cancel, btn_upload, btn_clear):
                try:
                    c.disabled = on
                except Exception:
                    pass
            page.update()

        # ===== Overlay (bloqueo total al guardar) =====
        scrim_msg = ft.Text("", color=ft.Colors.WHITE)
        scrim = ft.Container(
            visible=False,
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[ft.ProgressRing(), ft.Container(height=8), scrim_msg],
            ),
        )
        blockables = [t_id, t_nom, t_dir, t_des, ok, cancel, btn_upload, btn_clear]

        def _lock_panel(lock: bool, msg: str = ""):
            scrim.visible = lock
            scrim_msg.value = msg
            for c in blockables:
                try:
                    c.disabled = lock
                except Exception:
                    pass
            page.update()

        # ===== Rollback (borrar en Drive si no se llegó a guardar) =====
        pending_name = {"value": None}

        def _make_uploader():
            print("[ADD] _make_uploader()", flush=True)
            from back.integrations.drive_user_uploader import DriveUserUploader, DEFAULT_SCOPES
            try:
                up = DriveUserUploader.from_page(page)
                print("[ADD] _make_uploader: from_page OK", flush=True)
                return up
            except Exception as e1:
                print(f"[ADD] _make_uploader: from_page falló -> {e1}", flush=True)
                # Fallback con OAuthToken
                try:
                    tok = getattr(getattr(page, "auth", None), "token", None)
                    tk = None
                    if isinstance(tok, dict):
                        tk = tok
                    else:
                        at = getattr(tok, "access_token", None) or getattr(tok, "accessToken", None)
                        rt = getattr(tok, "refresh_token", None) or getattr(tok, "refreshToken", None)
                        scopes = getattr(tok, "scopes", None) or getattr(tok, "scope", None) or DEFAULT_SCOPES
                        if at:
                            tk = {"access_token": at, "refresh_token": rt, "scopes": scopes}
                    if not tk or not tk.get("access_token"):
                        raise RuntimeError("OAuthToken sin access_token")
                    from google.oauth2.credentials import Credentials
                    creds = Credentials(
                        token=tk.get("access_token"),
                        refresh_token=tk.get("refresh_token"),
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.getenv("GOOGLE_CLIENT_ID"),
                        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                        scopes=tk.get("scopes") or DEFAULT_SCOPES,
                    )
                    up = DriveUserUploader(credentials=creds)
                    print("[ADD] _make_uploader: fallback OK (OAuthToken)", flush=True)
                    return up
                except Exception as e2:
                    print(f"[ADD] _make_uploader: fallback falló -> {e2}", flush=True)
                    raise

        def _cleanup_drive_file(reason: str):
            try:
                fid = uploaded.get("file_id")
                if fid and not committed["image_committed"]:
                    print(f"[ADD] Cleanup Drive ({reason}) -> delete_file id={fid}", flush=True)
                    try:
                        uploader = _make_uploader()
                        uploader.delete_file(fid)
                        print(f"[ADD] Cleanup OK file_id={fid}", flush=True)
                    except Exception as ex:
                        print(f"[ADD] Cleanup WARN: no se pudo borrar en Drive file_id={fid}: {ex}", flush=True)
            finally:
                uploaded.update({"file_id": None, "view_link": None, "recid_img": None})

        def _dispose_picker(fp: ft.FilePicker):
            try:
                page.overlay.remove(fp)
                page.update()
            except Exception:
                pass

        async def _upload_only(local_path: str):
            """
            Sube al Drive del usuario (OAuth) y muestra el preview.
            NO escribe aún en Sheets (se “compromete” recién al guardar).
            """
            print(f"[ADD] _upload_only START path={local_path}", flush=True)
            try:
                uploader = _make_uploader()
                print("[ADD] Subiendo a Drive...", flush=True)
                file_id, view_link = await asyncio.to_thread(
                    uploader.upload_to_path, local_path, "TacticaGestorSheet/ImagenGestor", make_public=True
                )
                print(f"[ADD] Subida OK -> file_id={file_id} view_link={view_link}", flush=True)
            except Exception as e:
                _set_img_busy(False)
                page.snack_bar = ft.SnackBar(ft.Text(f"No se puede subir a Drive: {e}"))
                page.snack_bar.open = True; page.update()
                print(f"[ADD] ERROR upload -> {e}", flush=True)
                return

            uploaded["file_id"]   = file_id
            uploaded["view_link"] = view_link
            uploaded["recid_img"] = uuid4().hex[:10]

            try:
                preview.data["recid_imagen"] = view_link
                print("[ADD] Renderizar preview...", flush=True)
                renderizar_imagen_asinc(preview)
            except Exception as ex:
                print(f"[ADD] WARN render preview: {ex}", flush=True)

            _set_img_busy(False)
            btn_clear.disabled = False
            page.update()
            print("[ADD] _upload_only END", flush=True)

        def _on_pick_result(e: ft.FilePickerResultEvent, fp: ft.FilePicker):
            print(f"[ADD] pick_result -> files={len(e.files or [])}", flush=True)
            if not e.files:
                _set_img_busy(False)
                return
            f = e.files[0]
            print(f"[ADD] pick file: name={f.name} path={getattr(f,'path',None)}", flush=True)
            if f.path:
                page.run_task(_upload_only, f.path)
                return
            pending_name["value"] = f.name
            upload_url = page.get_upload_url(f.name, 600)
            print(f"[ADD] web -> get_upload_url ok, start upload name={f.name}", flush=True)
            fp.upload([ft.FilePickerUploadFile(name=f.name, upload_url=upload_url)])

        def _on_upload(e: ft.FilePickerUploadEvent):
            # Estilo nuevo
            if hasattr(e, "files") and e.files:
                for uf in e.files:
                    print(
                        f"[ADD] on_upload(new): name={getattr(uf,'name',None)} status={getattr(uf,'status',None)} "
                        f"progress={getattr(uf,'progress',None)} error={getattr(uf,'error',None)} path={getattr(uf,'path',None)}",
                        flush=True,
                    )
                    if getattr(uf, "error", None):
                        _set_img_busy(False)
                        page.snack_bar = ft.SnackBar(ft.Text(f"Error de subida: {uf.error}"))
                        page.snack_bar.open = True; page.update()
                        return
                    if getattr(uf, "status", None) != ft.FilePickerUploadStatus.COMPLETED and getattr(uf, "progress", 0) < 1:
                        return
                    local_path = getattr(uf, "path", None) or os.path.join(
                        UPLOAD_DIR, uf.name or pending_name["value"] or ""
                    )
                    print(f"[ADD] on_upload -> local_path={local_path}", flush=True)
                    page.run_task(_upload_only, local_path)
                return
            # Estilo viejo
            print(
                f"[ADD] on_upload(old): file_name={getattr(e,'file_name',None)} progress={getattr(e,'progress',None)} error={getattr(e,'error',None)}",
                flush=True,
            )
            if getattr(e, "error", None):
                _set_img_busy(False)
                page.snack_bar = ft.SnackBar(ft.Text(f"Error de subida: {e.error}"))
                page.snack_bar.open = True; page.update()
                return
            if getattr(e, "progress", None) is not None and e.progress < 1:
                return
            fname = getattr(e, "file_name", None) or getattr(e, "filename", None) or (pending_name["value"] or "")
            local_path = os.path.join(UPLOAD_DIR, fname)
            print(f"[ADD] on_upload(old) -> local_path={local_path}", flush=True)
            page.run_task(_upload_only, local_path)

        # Picker del panel (no interfiere con el global de EDIT)
        fp = ft.FilePicker(on_result=lambda ev: _on_pick_result(ev, fp), on_upload=_on_upload)
        page.overlay.append(fp); page.update()

        # ======= acciones imagen =======
        def _do_upload(_):
            print("[ADD] Intentando construir DriveUserUploader...", flush=True)
            try:
                _ = _make_uploader()
                print("[ADD] Uploader OK: vamos a subir a Drive.", flush=True)
            except Exception as e:
                print(f"[ADD] ERROR creando uploader: {e}", flush=True)
                _set_img_busy(False)
                page.snack_bar = ft.SnackBar(ft.Text(f"No se puede subir a Drive: {e}"))
                page.snack_bar.open = True; page.update()
                return
            _set_img_busy(True, "Subiendo imagen…")
            print("[ADD] Abrir file picker…", flush=True)
            fp.pick_files(allow_multiple=False, allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"])

        def _do_clear(_):
            print("[ADD] Quitar imagen (y cleanup si corresponde)…", flush=True)
            _cleanup_drive_file("clear_button")
            preview.data["recid_imagen"] = ""
            big_img.src = PREVIEW_PH
            page.update()
            btn_clear.disabled = True

        btn_upload.on_click = _do_upload
        btn_clear.on_click  = _do_clear

        # ======= acciones del panel =======
        def _really_close_bs():
            try:
                page.close(bs)
            except Exception:
                pass
            page.update()
            _dispose_picker(fp)

        def close_bs(_=None):
            print("[ADD] Cerrar panel (cancel) -> cleanup si no comprometido", flush=True)
            _cleanup_drive_file("cancel_or_close")
            _really_close_bs()

        def do_ok(_):
            iddep = (t_id.value or "").strip()
            nombre = (t_nom.value or "").strip()
            if not iddep or not nombre:
                page.snack_bar = ft.SnackBar(ft.Text("ID y Nombre son obligatorios."))
                page.snack_bar.open = True; page.update()
                return

            async def _save_flow():
                try:
                    # 🔒 Bloqueo TOTAL hasta cerrar
                    _lock_panel(True, "Guardando…")

                    # 1) Crear depósito
                    print(f"[ADD] Guardando depósito id={iddep} nombre={nombre}", flush=True)
                    recid_dep = backend.add(
                        id_deposito=iddep,
                        nombre_deposito=nombre,
                        direccion_deposito=(t_dir.value or "").strip(),
                        descripcion_deposito=(t_des.value or "").strip(),
                    )
                    print(f"[ADD] backend.add -> recid_dep={recid_dep}", flush=True)
                    if not recid_dep:
                        raise ValueError("No se pudo crear el depósito.")

                    # 2) Asociar imagen si existe
                    if uploaded["view_link"] and uploaded["recid_img"]:
                        recid_img = uploaded["recid_img"]
                        view_link = uploaded["view_link"]
                        print(f"[ADD] Vinculando imagen: recid_img={recid_img} view_link={view_link}", flush=True)

                        ok_img = False
                        ok_dep = False
                        try:
                            if getattr(backend, "api_img", None):
                                print("[ADD] api_img.add...", flush=True)
                                ok_img = backend.api_img.add(recid_img, view_link)
                                print(f"[ADD] api_img.add -> {ok_img}", flush=True)
                            if getattr(backend, "api", None):
                                print("[ADD] api.update_by_recid (set RecID_imagen)...", flush=True)
                                ok_dep = backend.api.update_by_recid(recid_dep, RecID_imagen=recid_img)
                                print(f"[ADD] api.update_by_recid -> {ok_dep}", flush=True)
                        except Exception as ex:
                            print(f"[ADD] ERROR asociando imagen -> {ex}", flush=True)
                            raise RuntimeError(f"Error asociando imagen: {ex}")

                        if not (ok_img and ok_dep):
                            print(f"[ADD] FALLO asociación imagen (ok_img={ok_img}, ok_dep={ok_dep}) -> cleanup", flush=True)
                            raise RuntimeError("No se pudo asociar la imagen al depósito.")

                        committed["image_committed"] = True
                        print("[ADD] Imagen comprometida en Sheets y vinculada al depósito.", flush=True)

                    # 3) Refrescar y cerrar
                    _safe_refresh()
                    render_list()
                    _really_close_bs()
                    page.snack_bar = ft.SnackBar(ft.Text("Depósito agregado."))
                    page.snack_bar.open = True; page.update()
                    print("[ADD] Guardado completo.", flush=True)

                except Exception as ex:
                    print(f"[ADD] ERROR guardando: {ex}", flush=True)
                    _cleanup_drive_file("save_error_rollback")
                    # 🔓 Desbloquear solo si hay error (para corregir)
                    _lock_panel(False, "")
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                    page.snack_bar.open = True; page.update()

            page.run_task(_save_flow)

        ok.on_click = do_ok
        cancel.on_click = close_bs

        # ======= LAYOUT: imagen primero + botones juntos, campos compactos =======
        image_actions = ft.Row(spacing=8, alignment=ft.MainAxisAlignment.START, controls=[btn_upload, btn_clear])

        form_fields = ft.Column(spacing=6, controls=[t_id, t_nom, t_dir, t_des])  # 👈 menos separación

        actions_row = ft.Row(alignment=ft.MainAxisAlignment.END, controls=[cancel, ok])

        inner = ft.Container(
            width=PANEL_W,
            padding=16,
            bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Agregar depósito", size=16, weight=ft.FontWeight.W_700),
                    image_actions,                # 👈 Cargar / Quitar juntos y primero
                    preview, load_bar, load_msg, drive_state_lbl,
                    form_fields,                  # 👈 campos más pegados
                    actions_row,
                ],
            ),
        )

        # Stack para poder superponer el scrim de bloqueo al Guardar
        panel_stack = ft.Stack(controls=[inner, scrim])

        def _on_bs_dismiss(_):
            print("[ADD] BottomSheet dismiss -> cleanup si no comprometido", flush=True)
            _cleanup_drive_file("sheet_dismiss")

        bs = ft.BottomSheet(
            content=ft.Container(alignment=ft.alignment.center, content=panel_stack),
            show_drag_handle=True,
            is_scroll_controlled=True,
        )
        try:
            bs.on_dismiss = _on_bs_dismiss
        except Exception:
            pass

        page.open(bs)


    # ----------------- panel editar (preview arriba + form abajo) -----------------
    def open_edit_panel(row_key: str):
        from back.sheet.tabGestor.imagen_asinc import renderizar_imagen_asinc
        from back.sheet.tabGestor.imagen_storage import delete_local_image_by_link

        # --- resolver el registro y su RecID real ---
        d = backend.depo_by_recid.get(row_key)
        if not d:
            for r in (backend.depositos or []):
                if r.get("RecID") == row_key or r.get("id_deposito") == row_key:
                    d = r
                    break
        if not d:
            print(f"[EDIT] open_edit_panel: NO ENCONTRADO row_key={row_key}", flush=True)
            page.snack_bar = ft.SnackBar(ft.Text(f"No se encontró el depósito ({row_key})."))
            page.snack_bar.open = True; page.update()
            return

        recid_real = (d.get("RecID") or "").strip()
        print(f"[EDIT] open_edit_panel -> row_key={row_key}  recid_real={recid_real}", flush=True)
        if not recid_real:
            page.snack_bar = ft.SnackBar(ft.Text("Registro sin RecID válido."))
            page.snack_bar.open = True; page.update()
            return

        # --- tamaños / constantes ---
        PREVIEW_W, PREVIEW_H = 300, 240
        PANEL_W = 480
        PREVIEW_PH = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )

        link_actual = (d.get("imagen_url") or "").strip()
        recid_imagen_val = (link_actual or d.get("RecID_imagen") or "").strip()

        # --- imagen + overlay (editar/eliminar imagen) ---
        big_img = ft.Image(
            src=PREVIEW_PH, width=PREVIEW_W, height=PREVIEW_H, fit=ft.ImageFit.COVER,
            error_content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=24, color=ft.Colors.GREY_600),
        )

        ov_ref = ft.Ref[ft.Container]()
        def _show_overlay(e):
            if ov_ref.current is None:
                return
            ov_ref.current.opacity = 1.0 if e.data == "true" else 0.0
            ov_ref.current.update()

        def _do_delete_image(_=None):
            print(f"[EDIT] Eliminar IMAGEN -> recid_deposito={recid_real} recid_img={recid_imagen_val}", flush=True)
            ok_sheet = backend.remove_image_for_deposito(recid_real)
            ok_file, tried, img_id = delete_local_image_by_link(link_actual)
            big_img.src = PREVIEW_PH; big_img.update()
            _safe_refresh(); render_list()
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Imagen eliminada. sheets={'OK' if ok_sheet else 'NO'}  file={'OK' if ok_file else 'NO'}  id={img_id or '-'}")
            )
            page.snack_bar.open = True; page.update()

        edit_img_btn = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED, tooltip="Editar imagen",
            icon_size=16, height=28, width=28, style=ft.ButtonStyle(padding=0),
            icon_color=ft.Colors.GREY_400,
        )
        del_img_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE, tooltip="Eliminar imagen",
            icon_size=16, height=28, width=28, style=ft.ButtonStyle(padding=0),
            icon_color=ft.Colors.GREY_400, on_click=_do_delete_image,
        )

        overlay_layer = ft.Container(
            ref=ov_ref, width=PREVIEW_W, height=PREVIEW_H, opacity=0, animate_opacity=200,
            alignment=ft.alignment.top_right, padding=6, bgcolor=None,
            content=ft.Row(spacing=6, alignment=ft.MainAxisAlignment.END, controls=[edit_img_btn, del_img_btn]),
        )

        preview_stack = ft.Stack(width=PREVIEW_W, height=PREVIEW_H, controls=[big_img, overlay_layer])

        # barra de carga + error del preview
        loading_bar = ft.ProgressBar(width=PREVIEW_W, visible=False)
        error_lbl   = ft.Text("", size=11, color=ft.Colors.RED_400, visible=False)

        preview = ft.Container(
            on_hover=_show_overlay,
            content=preview_stack,
            border_radius=12,
            padding=0,
            bgcolor=ft.Colors.WHITE,
            alignment=ft.alignment.center,
            data={
                "recid_imagen": recid_imagen_val,
                "img_control": big_img,
                "busy": loading_bar,
                "error_label": error_lbl,
            },
        )

        def _open_picker(_):
            print(f"[EDIT] EDITAR IMAGEN -> set pending_upload recid={recid_real}", flush=True)
            pending_upload["recid"] = recid_real
            pending_upload["preview"] = preview
            _set_upload_busy(preview, True)
            file_picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["jpg", "jpeg", "png", "webp", "gif"],
            )
        edit_img_btn.on_click = _open_picker

        # --- FORM (debajo) ---
        t_id  = ft.TextField(label="ID depósito", value=d.get("id_deposito", ""))
        t_nom = ft.TextField(label="Nombre",      value=d.get("nombre_deposito", ""))
        t_dir = ft.TextField(label="Dirección",   value=d.get("direccion_deposito", ""))
        t_des = ft.TextField(label="Descripción", value=d.get("descripcion_deposito", ""))

        for tf in (t_id, t_nom, t_dir, t_des):
            tf.width = None
            tf.expand = True

        ok              = ft.FilledButton("Guardar", icon=ft.Icons.SAVE, style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE))
        btn_delete_depo = ft.FilledTonalButton("Eliminar", icon=ft.Icons.DELETE_OUTLINE)
        cancel          = ft.OutlinedButton("Cerrar")

        # --- overlay de bloqueo del panel + mensaje ---
        scrim_msg = ft.Text("", color=ft.Colors.WHITE)
        scrim = ft.Container(
            visible=False,
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[ft.ProgressRing(), ft.Container(height=8), scrim_msg],
            ),
        )
        delete_busy = ft.ProgressBar(visible=False)
        blockables = [t_id, t_nom, t_dir, t_des, ok, btn_delete_depo, cancel, edit_img_btn, del_img_btn]

        def _lock_panel(lock: bool, msg: str = ""):
            scrim.visible = lock
            scrim_msg.value = msg
            delete_busy.visible = lock
            for c in blockables:
                try:
                    c.disabled = lock
                except Exception:
                    pass
            page.update()

        # contenido del panel
        panel_col = ft.Column(
            spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Editar depósito", size=16, weight=ft.FontWeight.W_700),
                preview, loading_bar, error_lbl,
                ft.Column(
                    spacing=12,
                    controls=[
                        t_id, t_nom, t_dir, t_des,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[btn_delete_depo, ft.Row(controls=[cancel, ok])]
                        ),
                        delete_busy,
                    ],
                ),
            ],
        )
        panel_container = ft.Container(width=PANEL_W, padding=16, bgcolor=WHITE, content=panel_col)
        panel_stack = ft.Stack(controls=[panel_container, scrim])

        bs = ft.BottomSheet(
            content=ft.Container(alignment=ft.alignment.center, content=panel_stack),
            show_drag_handle=True,
            is_scroll_controlled=True,
        )
        page.open(bs)

        async def _kick_preview():
            await asyncio.sleep(0)
            if recid_imagen_val:
                renderizar_imagen_asinc(preview)
        _run_task(_kick_preview)

        # ---- CRUD con RecID real ----
        def close_bs(_=None):
            page.close(bs); page.update()

        def do_save(_):
            print(f"[EDIT] Guardar CLICK -> recid_real={recid_real}", flush=True)
            _lock_panel(True, "Guardando…")
            try:
                iddep = (t_id.value or "").strip()
                nombre = (t_nom.value or "").strip()
                if not iddep or not nombre:
                    page.snack_bar = ft.SnackBar(ft.Text("ID y Nombre son obligatorios."))
                    page.snack_bar.open = True; page.update(); return
                okb = backend.update(
                    recid_real,
                    id_deposito=iddep,
                    nombre_deposito=nombre,
                    direccion_deposito=(t_dir.value or "").strip(),
                    descripcion_deposito=(t_des.value or "").strip(),
                )
                print(f"[EDIT] backend.update({recid_real}) -> {okb}", flush=True)
                if not okb:
                    raise ValueError("No se pudo guardar.")
                _safe_refresh(); render_list(); close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Cambios guardados."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                print(f"[EDIT] ERROR guardando recid={recid_real}: {ex}", flush=True)
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                _lock_panel(False)

        def _close_dlg(dlg):
            # cierre seguro del diálogo
            try:
                page.close(dlg)
            except Exception:
                # fallback por si close lanza en tu versión
                dlg.open = False
            page.update()

        def _confirm_delete(dlg):
            print(f"[EDIT] Confirmar ELIMINAR -> recid_real={recid_real}", flush=True)
            _close_dlg(dlg)

            async def _do():
                try:
                    _lock_panel(True, "Eliminando…")
                    print(f"[EDIT] calling backend.delete({recid_real}) ...", flush=True)
                    okb = await asyncio.to_thread(backend.delete, recid_real)
                    print(f"[EDIT] backend.delete({recid_real}) -> {okb}", flush=True)
                    if not okb:
                        raise RuntimeError("No se pudo eliminar.")

                    # Quitar de caches locales inmediatamente
                    try:
                        if hasattr(backend, "depositos") and isinstance(backend.depositos, list):
                            backend.depositos = [r for r in backend.depositos if (r.get("RecID") or "") != recid_real]
                        if hasattr(backend, "depo_by_recid") and isinstance(backend.depo_by_recid, dict):
                            backend.depo_by_recid.pop(recid_real, None)
                    except Exception as _ex:
                        print(f"[EDIT] WARN limpiando caches locales: {_ex}", flush=True)

                    _safe_refresh()
                    render_list()

                    page.close(bs)  # cerrar el panel ya que el registro ya no existe
                    page.snack_bar = ft.SnackBar(ft.Text("Depósito eliminado."))
                    page.snack_bar.open = True; page.update()
                except Exception as ex:
                    print(f"[EDIT] ERROR eliminando recid={recid_real}: {ex}", flush=True)
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error al eliminar: {ex}"))
                    page.snack_bar.open = True; page.update()
                finally:
                    _lock_panel(False)
            _run_task(_do)

        def _on_btn_delete_click(e):
            print(f"[EDIT] Botón ELIMINAR CLICK -> recid_real={recid_real}", flush=True)
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirmar eliminación"),
                content=ft.Text("¿Eliminar este depósito? Esta acción no se puede deshacer."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda __: (_close_dlg(dlg))),
                    ft.TextButton("Eliminar", on_click=lambda __: (_confirm_delete(dlg))),
                ],
            )
            # 👇 CLAVE: en lugar de page.dialog=...; dlg.open=True; page.update()
            page.open(dlg)

        ok.on_click = do_save
        btn_delete_depo.on_click = _on_btn_delete_click
        cancel.on_click = close_bs
        print(f"[EDIT] Handlers bindeados (recid={recid_real}).", flush=True)

    # ----------------- layout principal -----------------
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[ft.Text("Depósitos", size=22, weight=ft.FontWeight.W_700), status],
    )
    btn_add = ft.FilledButton(
        "Agregar depósito", icon=ft.Icons.ADD,
        style=ft.ButtonStyle(bgcolor=PRIMARY, color=WHITE),
        on_click=open_add_panel,
    )
    right_controls = ft.Row(alignment=ft.MainAxisAlignment.END, controls=[filter_btn])
    action_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[btn_add, right_controls])

    root = ft.Container(
        bgcolor=ft.Colors.GREY_50,
        expand=True,
        border_radius=12,
        padding=16,
        content=ft.Column(
            spacing=10,
            expand=True,
            controls=[header, search, action_row, ft.Container(expand=True, content=lv_holder)],
        ),
    )

    print("[DepositoUI] backend:", type(backend), getattr(backend, "__module__", "?"), flush=True)
    _safe_refresh()
    render_list()

    if bus:
        try:
            bus.subscribe("depositos_changed", lambda _=None: (_safe_refresh(), render_list()))
        except Exception:
            pass

    return root
