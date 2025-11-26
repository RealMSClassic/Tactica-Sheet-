# front/ventana_sheets.py
import flet as ft
from datetime import datetime
from googleapiclient.errors import HttpError
import json, base64, requests

from back.sheet.usuario_api import UsuarioAPI

from front.ventana_sheet_item_actions_bs import (
    open_rename_index_bs,
    open_delete_index_bs,
)

from back.drive.drive_check import (
    get_or_create_folder_id,
    get_or_create_index_sheet,
    build_sheets_service,
    build_drive_service,   # por si lo necesitás en otros flujos
)

from back.sheets_ops import (
    create_spreadsheet_with_structure,
    append_index_row,
    DEFAULT_SHEET_DATA,
    rename_file_in_drive,
    trash_file_in_drive,
    update_index_name_by_sheet_id,
    clear_index_row_by_sheet_id,
)

# ------------------- Helpers de identidad -------------------
def _jwt_payload(tok: str) -> dict:
    """Decodifica (sin verificar) el payload de un JWT para leer claims."""
    try:
        p = tok.split(".")
        if len(p) < 2:
            return {}
        b = p[1] + "=" * (-len(p[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(b.encode()))
    except Exception:
        return {}

def _userinfo_from_google(access_token: str) -> dict:
    """Lee /userinfo de Google usando el access token (requiere scopes email y profile)."""
    try:
        url = "https://openidconnect.googleapis.com/v1/userinfo"
        r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        if r.status_code == 200:
            return r.json() or {}
    except Exception:
        pass
    return {}

def get_identity_from_token(page):
    """
    Devuelve (name, email, uid) usando, en este orden:
    - Claims del id_token (si lo hay)
    - token.claims / token.userinfo si el provider ya los puso
    - /userinfo con el access_token como fallback
    - page.auth.user como último recurso
    """
    t = getattr(page.auth, "token", None)
    claims: dict = {}

    # 1) Preferimos claims del id_token (si existe)
    raw_id = getattr(t, "id_token", None)
    if isinstance(raw_id, str):
        claims = _jwt_payload(raw_id) or {}

    # 2) Si el objeto token trae claims/userinfo, los usamos
    if not claims and t is not None:
        for attr in ("claims", "idinfo", "id_info", "userinfo", "user_info"):
            maybe = getattr(t, attr, None)
            if isinstance(maybe, dict) and maybe:
                claims = maybe
                break

    name  = (claims.get("name")
             or claims.get("given_name")
             or claims.get("preferred_username"))
    email = (claims.get("email")
             or claims.get("upn")
             or claims.get("preferred_username"))
    uid   = (claims.get("sub")
             or claims.get("oid")
             or claims.get("id"))

    # 3) Fallback: /userinfo si falta name o email
    if (not name or not email) and t is not None:
        at = getattr(t, "access_token", None)
        if isinstance(at, str) and at:
            ui = _userinfo_from_google(at)
            if ui:
                name  = name  or ui.get("name") or ui.get("given_name")
                email = email or ui.get("email")
                uid   = uid   or ui.get("sub")

    # 4) Último recurso: page.auth.user
    u = getattr(page.auth, "user", None)
    name  = name  or getattr(u, "name", None)
    email = email or getattr(u, "email", None)
    uid   = uid   or getattr(u, "id", None)

    # Debug
    print("=== TOKEN CLAIMS DEBUG ===")
    print("name:", name, "| email:", email, "| uid:", uid)
    if not (name or email or uid):
        print("claims crudos:", claims)

    return name, email, uid

# ------------------- Vista principal -------------------
def sheets_selector_view(page: ft.Page, on_select=None) -> ft.View:
    RED = "#E53935"; RED_DARK = "#C62828"; BG = "#F7F7F7"; WHITE = ft.Colors.WHITE
    TARGET_FOLDER = "TacticaGestorSheet"
    INDEX_NAME = "indexSheetList"

    # Identidad para saludo y para cache cross-módulo
    name, email, uid = get_identity_from_token(page)
    display_name = name or email or uid or "Invitado"
    page.session.set("user_name", display_name)
    page.session.set("user_email", email or "")
    page.session.set("user_uid", uid or "")
    page.client_storage.set("user_name", display_name)
    page.client_storage.set("user_email", email or "")
    page.client_storage.set("user_uid", uid or "")

    all_items: list[dict] = []
    filtered: list[dict] = []
    status_txt = ft.Text("", size=12, color=ft.Colors.GREY_600)

    search = ft.TextField(
        hint_text="Buscar por nombre o ID...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED_DARK,
        content_padding=10,
        disabled=True,
    )

    lv = ft.ListView(spacing=10, auto_scroll=False, expand=1)

    # ===== Overlay de carga pantalla completa =====
    loading_msg = ft.Text("Cargando Sheet…", size=18, color=WHITE)
    loading_overlay = ft.Container(
        visible=False,
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
        alignment=ft.alignment.center,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[ft.ProgressRing(width=36, height=36), ft.Container(height=12), loading_msg],
        ),
    )

    def show_loading(text: str = "Cargando Sheet…"):
        loading_msg.value = text
        loading_overlay.visible = True
        page.update()

    def hide_loading():
        loading_overlay.visible = False
        page.update()

    # --------- Chequeo de acceso (Sheets) ---------
    def _user_can_access_sheet(page: ft.Page, sheet_id: str) -> tuple[bool, str]:
        """
        Devuelve (ok, msg) verificando acceso con la API de Sheets.
        """
        try:
            svc = build_sheets_service(page)
            svc.spreadsheets().get(spreadsheetId=sheet_id, fields="spreadsheetId").execute()
            return True, ""
        except HttpError as he:
            msg = "The caller does not have permission" if he.resp.status == 403 else "Archivo no encontrado o sin acceso"
            return False, msg
        except Exception as ex:
            return False, str(ex)

    # ---------- helpers ----------
    def extract_id(item: dict) -> str | None:
        return (item or {}).get("id") or item.get("spreadsheetId") or item.get("sheet_id")

    # ---------- Diálogo de acceso denegado ----------
    def _show_access_denied_dialog(sheet_id: str, raw_msg: str):
        me_email = page.session.get("user_email") or page.client_storage.get("user_email") or ""
        txt = ft.Text(
            f"No tenés acceso a este Sheet.\n\n"
            f"ID: {sheet_id}\n"
            f"Usuario actual: {me_email or '(desconocido)'}\n\n"
            f"Detalle técnico: {raw_msg}",
            size=13
        )
        ok_btn = ft.FilledButton("Entendido", icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        dlg = ft.AlertDialog(modal=True, content=ft.Container(padding=16, content=ft.Column(spacing=12, controls=[txt, ok_btn])))
        def _close(_=None):
            try:
                dlg.open = False
                page.update()
            except Exception:
                pass
        ok_btn.on_click = _close
        page.dialog = dlg
        dlg.open = True
        page.update()

    # ---------- Al seleccionar un sheet ----------
    def _open_selected_sheet(it: dict):
        sid = (extract_id(it) or "").strip()
        if not sid:
            page.snack_bar = ft.SnackBar(ft.Text("Item inválido (sin ID)."))
            page.snack_bar.open = True
            page.update()
            return

        # Mostrar overlay bloqueando toda la ventana
        show_loading("Cargando Sheet…")

        try:
            ok, msg = _user_can_access_sheet(page, sid)
            if not ok:
                hide_loading()
                _show_access_denied_dialog(sid, msg)
                return

            # obtener el título real (si falla, uso el name del item)
            try:
                svc = build_sheets_service(page)
                meta = svc.spreadsheets().get(
                    spreadsheetId=sid, fields="properties(title)"
                ).execute()
                title = meta.get("properties", {}).get("title", "") or it.get("name", "")
            except Exception:
                title = it.get("name", "")

            # Guardar selección (session + client_storage)
            page.session.set("sheet_id", sid)
            page.session.set("last_sheet_id", sid)
            page.session.set("sheet_name", title)
            page.client_storage.set("active_sheet_id", sid)
            page.client_storage.set("active_sheet_name", title)

            # NO ocultamos el overlay acá: la vista cambia y el overlay desaparece con este View
            page.go("/panel_window")

        except Exception as ex:
            hide_loading()
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al conectar: {ex}"))
            page.snack_bar.open = True
            page.update()

    # 🔧 Handler efectivo (externo o interno)
    select_handler = on_select or _open_selected_sheet

    # ---------- BottomSheet "Agregar" ----------
    def open_add_bottom_sheet(_=None):
        rg_mode = ft.RadioGroup(
            value="nuevo",
            content=ft.Row(
                tight=True,
                controls=[
                    ft.Radio(value="nuevo", label="Crear nuevo sheet"),
                    ft.Radio(value="enlace", label="Añadir por link/ID"),
                ],
            ),
        )

        tf_name = ft.TextField(
            label="Nombre del Sheet",
            hint_text="Ej.: Inventario Sucursal Norte",
            autofocus=True,
            border_radius=12,
            filled=True,
            bgcolor=ft.Colors.WHITE,
            width=420,
            visible=True,
        )
        tf_link = ft.TextField(
            label="Enlace o ID de Google Sheets",
            hint_text="Pega la URL completa o solo el ID",
            prefix_icon=ft.Icons.LINK,
            border_radius=12,
            filled=True,
            bgcolor=ft.Colors.WHITE,
            width=420,
            visible=False,
        )

        busy = ft.ProgressBar(visible=False, width=420)
        btn_cancel = ft.OutlinedButton("Cancelar")
        btn_confirm = ft.FilledButton(
            "Crear",
            icon=ft.Icons.CHECK,
            style=ft.ButtonStyle(
                bgcolor=RED, color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=12), elevation=3,
            ),
        )

        content = ft.Container(
            padding=ft.padding.all(16),
            bgcolor=ft.Colors.WHITE,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Agregar Sheet", size=18, weight=ft.FontWeight.W_600),
                    rg_mode,
                    tf_name,
                    tf_link,
                    busy,
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_confirm]),
                ],
            ),
        )

        bs = ft.BottomSheet(
            content=content,
            show_drag_handle=True,
            is_scroll_controlled=True,
            on_dismiss=lambda e: page.update(),
        )
        page.open(bs)

        def on_mode_change(_):
            is_new = rg_mode.value == "nuevo"
            tf_name.visible = is_new
            tf_link.visible = not is_new
            btn_confirm.text = "Crear" if is_new else "Añadir"
            page.update()

        rg_mode.on_change = on_mode_change

        def extract_sheet_id(s: str) -> str | None:
            import re
            s = (s or "").strip()
            if not s:
                return None
            m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", s)
            if m:
                return m.group(1)
            if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", s):
                return s
            return None

        def close_bs(_=None):
            try:
                page.close(bs)
            except Exception:
                bs.open = False
            page.update()

        def do_confirm(_):
            is_new = rg_mode.value == "nuevo"
            folder_id = page.client_storage.get("tactica_folder_id")
            index_id = page.client_storage.get("tactica_index_sheet_id")
            if not folder_id or not index_id:
                page.snack_bar = ft.SnackBar(ft.Text("No hay carpeta/índice disponible."))
                page.snack_bar.open = True
                page.update()
                return

            busy.visible = True
            btn_confirm.disabled = True
            btn_cancel.disabled = True
            page.update()
            try:
                if is_new:
                    name = (tf_name.value or "").strip()
                    if not name:
                        raise ValueError("Ingresá un nombre.")

                    new_sheet_id = create_spreadsheet_with_structure(
                        page, folder_id, name, DEFAULT_SHEET_DATA
                    )

                    # Intento sembrar usuarios (admin) — no crítico si falla
                    try:
                        UsuarioAPI(page, new_sheet_id).seed_admin_from_auth()
                    except Exception as seed_ex:
                        page.snack_bar = ft.SnackBar(ft.Text(f"Atención: no se pudo sembrar 'usuarios' ({seed_ex})."))
                        page.snack_bar.open = True

                    correo = getattr(getattr(page.auth, "user", None), "email", "") or ""
                    append_index_row(page, index_id, name, new_sheet_id, correo, "Creador")

                    created = datetime.now().strftime("%d/%m/%Y")
                    new_item = {"name": name, "id": new_sheet_id, "created": created, "estado": "Creador"}
                    filtered.append(new_item)
                    all_items.append(new_item)

                else:
                    raw = (tf_link.value or "").strip()
                    sid = extract_sheet_id(raw)
                    if not sid:
                        raise ValueError("Link/ID inválido.")

                    sheets = build_sheets_service(page)
                    meta = sheets.spreadsheets().get(
                        spreadsheetId=sid, fields="properties(title)"
                    ).execute()
                    sheet_name = meta["properties"]["title"]

                    if any(it.get("id") == sid for it in all_items):
                        raise ValueError("Ese sheet ya está en la lista.")

                    correo = getattr(getattr(page.auth, "user", None), "email", "") or ""
                    append_index_row(page, index_id, sheet_name, sid, correo, "Invitado")

                    created = datetime.now().strftime("%d/%m/%Y")
                    new_item = {"name": sheet_name, "id": sid, "created": created, "estado": "Invitado"}
                    filtered.append(new_item)
                    all_items.append(new_item)

                refresh_list(True)
                close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Operación realizada correctamente."))
                page.snack_bar.open = True
                page.update()

            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True
                page.update()
            finally:
                busy.visible = False
                btn_confirm.disabled = False
                btn_cancel.disabled = False
                page.update()

        btn_confirm.on_click = do_confirm
        btn_cancel.on_click = close_bs

    # ---------- render de lista ----------
    ITEM_HEIGHT = 110
    LEFT_W = 56
    RIGHT_W = 100
    GAP = 10

    def build_item(it: dict) -> ft.Control:
        estado_norm = (it.get("estado", "") or "").strip().lower()
        if estado_norm in ("creador", "administrador"):
            row_bg = WHITE
        elif estado_norm == "invitado":
            row_bg = ft.Colors.LIGHT_BLUE_50
        elif estado_norm == "no existe":
            row_bg = ft.Colors.BLUE_GREY_50
        else:
            row_bg = WHITE

        def action_button(icon_name, tooltip, handler):
            return ft.Container(
                width=44, height=44, alignment=ft.alignment.center,
                content=ft.IconButton(
                    icon=icon_name, icon_size=22, tooltip=tooltip,
                    style=ft.ButtonStyle(padding=ft.padding.all(0), mouse_cursor=ft.MouseCursor.CLICK),
                    on_click=handler,
                ),
            )

        def _after_rename(updated_item: dict):
            for lst in (all_items, filtered):
                for x in lst:
                    if x["id"] == updated_item["id"]:
                        x["name"] = updated_item["name"]
            refresh_list(True)

        def _after_delete(deleted_item: dict):
            all_items[:] = [x for x in all_items if x["id"] != deleted_item["id"]]
            filtered[:] = [x for x in filtered if x["id"] != deleted_item["id"]]
            refresh_list(True)

        actions = ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.END,
            controls=[
                action_button(
                    ft.Icons.DRIVE_FILE_RENAME_OUTLINE, "Renombrar",
                    lambda e, it=it: open_rename_index_bs(page, it, on_done=_after_rename)
                ),
                action_button(
                    ft.Icons.DELETE_OUTLINE, "Eliminar",
                    lambda e, it=it: open_delete_index_bs(page, it, on_done=_after_delete)
                ),
            ],
        )

        left_block = ft.Container(
            width=LEFT_W, alignment=ft.alignment.center_left,
            content=ft.Container(
                width=44, height=44, bgcolor=ft.Colors.RED_50, border_radius=22,
                alignment=ft.alignment.center,
                content=ft.Icon(name=ft.Icons.TABLE_CHART_OUTLINED, color=RED),
            ),
        )

        middle_block = ft.Container(
            expand=True,
            content=ft.Column(
                spacing=4, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Text(it["name"], size=18, weight=ft.FontWeight.W_500, color=ft.Colors.BLACK87,
                            no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f'ID : {extract_id(it) or ""}', size=12, color=ft.Colors.GREY_600,
                            no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Creado: {it.get('created', '')}", size=11, color=ft.Colors.GREY_500,
                            no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ],
            ),
            on_click=lambda e, item=it: select_handler(item),
        )

        right_block = ft.Container(width=RIGHT_W, alignment=ft.alignment.center_right, content=actions)

        return ft.Container(
            expand=True, height=ITEM_HEIGHT, bgcolor=row_bg,
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            content=ft.Row(
                spacing=GAP, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[left_block, middle_block, right_block],
            ),
        )

    def refresh_list(with_update: bool = False):
        lv.controls = [build_item(it) for it in filtered]
        status_txt.value = f"Index: {len(all_items)} | render: {len(lv.controls)}"
        if with_update:
            page.update()

    def on_search_change(e):
        q = (search.value or "").lower().strip()
        filtered.clear()
        if not q:
            filtered.extend(all_items)
        else:
            filtered.extend([it for it in all_items if q in (it["name"] or "").lower() or q in (extract_id(it) or "")])
        refresh_list(True)

    search.on_change = on_search_change

    # ---------- leer índice ----------
    def _read_index_rows(index_sheet_id: str) -> list[dict]:
        sheets = build_sheets_service(page)
        resp = sheets.spreadsheets().values().get(
            spreadsheetId=index_sheet_id,
            range="C2:G"
        ).execute()

        rows = resp.get("values", []) or []
        out = []
        for r in rows:
            name = (r[0].strip() if len(r) > 0 else "")
            sid  = (r[1].strip() if len(r) > 1 else "")
            estado = (r[3].strip() if len(r) > 3 else "")
            raw_date = (r[4].strip() if len(r) > 4 else "")

            created = ""
            if raw_date:
                try:
                    dt = datetime.strptime(raw_date, "%d/%m/%Y %H:%M:%S")
                    created = dt.strftime("%d/%m/%Y")
                except Exception:
                    created = (raw_date.split(" ")[0] if " " in raw_date else raw_date)
            if name and sid:
                out.append({"name": name, "id": sid, "created": created, "estado": estado})
        return out

    def init_load():
        t = getattr(page.auth, "token", None)
        if not (t and getattr(t, "access_token", None)):
            status_txt.value = "Iniciá sesión para ver tus Sheets."
            page.update()
            return
        try:
            folder_id = get_or_create_folder_id(page, TARGET_FOLDER)
            page.client_storage.set("tactica_folder_id", folder_id)

            index_id = get_or_create_index_sheet(page, folder_id, index_name=INDEX_NAME)
            page.client_storage.set("tactica_index_sheet_id", index_id)

            items = _read_index_rows(index_id)
            all_items[:] = items
            filtered[:] = items
            search.disabled = False
            refresh_list(False)
        except Exception as ex:
            search.disabled = True
            all_items.clear()
            filtered.clear()
            status_txt.value = f"Error cargando lista: {ex}"

    # ---------- layout ----------
    body = ft.Container(
        bgcolor=BG, expand=True,
        content=ft.Column(
            spacing=8, expand=True,
            controls=[
                ft.Container(padding=ft.padding.only(left=16, top=10, right=16, bottom=0), content=status_txt),
                ft.Container(padding=ft.padding.only(left=16, top=6, right=16, bottom=8), content=search),
                ft.Container(expand=True, content=lv),
            ],
        ),
    )

    add_bar = ft.Container(
        padding=ft.padding.all(16),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.FilledButton(
                    text="Agregar",
                    icon=ft.Icons.ADD,
                    style=ft.ButtonStyle(
                        bgcolor=RED, color=WHITE,
                        shape=ft.RoundedRectangleBorder(radius=12), elevation=3,
                    ),
                    on_click=open_add_bottom_sheet,
                )
            ],
        ),
    )

    # Apilamos contenido + overlay de carga
    content_column = ft.Column(spacing=0, controls=[body, add_bar])
    stack = ft.Stack(expand=True, controls=[content_column, loading_overlay])

    view = ft.View(
        route="/sheets",
        appbar=ft.AppBar(
            leading=ft.Container(width=1, height=1),
            title=ft.Text(
                f"Bienvenido: {display_name}",
                color=WHITE, size=20, weight=ft.FontWeight.W_600
            ),
            bgcolor=RED,
            center_title=False,
        ),
        controls=[stack],
    )

    init_load()
    return view
