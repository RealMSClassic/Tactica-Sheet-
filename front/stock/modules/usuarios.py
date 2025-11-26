# front/stock/modules/usuarios.py
import flet as ft
from typing import List, Dict
import re
from back.sheet.usuario_api import UsuarioAPI
from back.drive.permissions import upsert_user_permission, sheet_web_link

RED = "#E53935"
WHITE = ft.Colors.WHITE
def _is_gmail(email: str) -> bool:
    e = (email or "").strip().lower()
    # solo @gmail.com
    return re.fullmatch(r"[a-z0-9._%+\-]+@gmail\.com", e) is not None

def usuarios_view(page: ft.Page) -> ft.Control:
    sheet_id = (
        page.client_storage.get("active_sheet_id")
        or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
    )

    api = UsuarioAPI(page, sheet_id)

    usuarios: List[Dict] = []
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)

    search = ft.TextField(
        hint_text="Buscar por nombre o correo...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED,
        content_padding=10,
    )

    lv = ft.ListView(spacing=8, expand=True, auto_scroll=False)

    def load_list():
        nonlocal usuarios
        usuarios = api.list()
        render_list()

    def render_list():
        lv.controls.clear()
        q = (search.value or "").strip().lower()

        def matches(u: Dict) -> bool:
            campos = [
                (u.get("nombre_usuario") or "").lower(),
                (u.get("correo_usuario") or "").lower(),
                (u.get("rango_usuario") or "").lower(),
            ]
            return not q or any(q in c for c in campos)

        data = [u for u in usuarios if matches(u)]

        for u in data:
            lv.controls.append(_row_user(u))

        status.value = f"Usuarios: {len(usuarios)} | Mostrando: {len(data)}"
        page.update()

    def _row_user(u: Dict) -> ft.Control:
        nombre = u.get("nombre_usuario", "")
        correo = u.get("correo_usuario", "")
        rango = u.get("rango_usuario", "")

        def on_click(_=None, row=u):
            open_user_panel(row)

        return ft.Container(
            on_click=on_click,
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
                            ft.Text(nombre, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87),
                            ft.Text(correo, size=12, color=ft.Colors.GREY_700),
                        ],
                    ),
                    ft.Text(rango or "-", size=12, color=ft.Colors.GREY_600),
                ],
            ),
        )

    def on_search_change(_):
        render_list()

    search.on_change = on_search_change

    # ---------------- Panel usuario (editar / eliminar) ----------------
    def open_user_panel(user: Dict):
        recid = str(user.get("RecID", "") or "").strip()
        if not recid:
            page.snack_bar = ft.SnackBar(ft.Text("No se encontró RecID del usuario."))
            page.snack_bar.open = True
            page.update()
            return

        t_nombre = ft.TextField(
            label="Nombre", width=420, filled=True, bgcolor=WHITE,
            value=user.get("nombre_usuario", "")
        )
        t_correo = ft.TextField(
            label="Correo", width=420, filled=True, bgcolor=WHITE,
            value=user.get("correo_usuario", "")
        )

        is_admin = (user.get("rango_usuario") or "").strip().lower() == "administrador"
        dd_rango = ft.Dropdown(
            label="Rango",
            width=420,
            value=user.get("rango_usuario") or "",
            options=[
                ft.dropdown.Option("Administrador"),
                ft.dropdown.Option("Editor"),
                ft.dropdown.Option("Visitante"),
            ],
            disabled=is_admin,  # si es admin, no permitir cambiar
        )
        busy = ft.ProgressBar(visible=False, width=420)

        btn_save  = ft.FilledButton("Guardar",  icon=ft.Icons.SAVE,   style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_del   = ft.FilledButton("Eliminar", icon=ft.Icons.DELETE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_close = ft.OutlinedButton("Cerrar")

        content = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Editar usuario", size=18, weight=ft.FontWeight.W_700),
                    t_nombre, t_correo, dd_rango, busy,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[btn_del, ft.Row(controls=[btn_close, btn_save])]
                    ),
                ],
            ),
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True, elevation=8)
        page.open(bs)

        def close_bs(_=None):
            try:
                page.close(bs)
            except Exception:
                bs.open = False
            page.update()

        def do_save(_e, rid: str):
            nombre = (t_nombre.value or "").strip()
            correo = (t_correo.value or "").strip()
            rango  = (dd_rango.value or "").strip()
            if is_admin:
                rango = user.get("rango_usuario") or "Administrador"

            if not nombre or not correo:
                page.snack_bar = ft.SnackBar(ft.Text("Completá nombre y correo."))
                page.snack_bar.open = True; page.update(); return
            if "@" not in correo or "." not in correo.split("@")[-1]:
                page.snack_bar = ft.SnackBar(ft.Text("Correo inválido."))
                page.snack_bar.open = True; page.update(); return
            if not _is_gmail(correo):
                page.snack_bar = ft.SnackBar(ft.Text("Solo se aceptan correos @gmail.com."))
                page.snack_bar.open = True; page.update(); return
            busy.visible = True
            btn_save.disabled = True
            btn_del.disabled = True
            btn_close.disabled = True
            page.update()
            try:
                ok = api.update_by_recid(
                    rid,
                    nombre_usuario=nombre,
                    correo_usuario=correo,
                    rango_usuario=rango
                )
                if not ok:
                    raise ValueError("No se pudo actualizar el usuario.")

                # Sincronizar permiso con Drive (no bloquea si falla)
                try:
                    upsert_user_permission(page, sheet_id, correo, rango, send_email=False)
                except Exception as ex_perm:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Atención: permiso de Drive no actualizado ({ex_perm})."))
                    page.snack_bar.open = True

                load_list()
                close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Usuario actualizado."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False
                btn_save.disabled = False
                btn_del.disabled = False
                btn_close.disabled = False
                page.update()

        def do_delete(_):
            confirm_txt = ft.Text("¿Eliminar este usuario? Esta acción no se puede deshacer.")
            confirm_ok = ft.FilledButton("Eliminar", icon=ft.Icons.DELETE, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
            confirm_cancel = ft.OutlinedButton("Cancelar")

            inner = ft.Container(
                padding=16, bgcolor=WHITE,
                content=ft.Column(
                    spacing=10,
                    controls=[confirm_txt, ft.Row(alignment=ft.MainAxisAlignment.END, controls=[confirm_cancel, confirm_ok])]
                )
            )
            bs2 = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
            page.open(bs2)

            def close_bs2(_=None):
                try:
                    page.close(bs2)
                except Exception:
                    bs2.open = False
                page.update()

            def really_delete(_):
                try:
                    ok = api.delete_by_recid(recid)
                    if not ok:
                        raise ValueError("No se pudo eliminar.")
                    load_list()
                    close_bs2(); close_bs()
                    page.snack_bar = ft.SnackBar(ft.Text("Usuario eliminado."))
                    page.snack_bar.open = True; page.update()
                except Exception as ex:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                    page.snack_bar.open = True; page.update()

            confirm_ok.on_click = really_delete
            confirm_cancel.on_click = close_bs2

        btn_save.on_click  = lambda e, rid=recid: do_save(e, rid)
        btn_del.on_click   = do_delete
        btn_close.on_click = close_bs
        t_nombre.on_submit = lambda e, rid=recid: do_save(e, rid)
        t_correo.on_submit = lambda e, rid=recid: do_save(e, rid)
        page.update()

    # ---------------- Agregar usuario ----------------
    def open_add_user(_=None):
        t_nombre = ft.TextField(label="Nombre", width=420, filled=True, bgcolor=WHITE, autofocus=True)
        t_correo = ft.TextField(label="Correo", width=420, filled=True, bgcolor=WHITE)
        dd_rango = ft.Dropdown(
            label="Rango",
            width=420,
            options=[ft.dropdown.Option("Editor"), ft.dropdown.Option("Visitante")],
            value="Visitante",
        )
        busy = ft.ProgressBar(visible=False, width=420)

        btn_ok = ft.FilledButton("Agregar", icon=ft.Icons.CHECK, style=ft.ButtonStyle(bgcolor=RED, color=WHITE))
        btn_cancel = ft.OutlinedButton("Cancelar")

        content = ft.Container(
            padding=16, bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Text("Agregar usuario", size=18, weight=ft.FontWeight.W_700),
                    t_nombre, t_correo, dd_rango, busy,
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
                ],
            ),
        )
        bs = ft.BottomSheet(content=content, show_drag_handle=True, is_scroll_controlled=True, elevation=8)
        page.open(bs)

        def close_bs():
            try:
                page.close(bs)
            except Exception:
                bs.open = False
            page.update()

        def _next_user_id() -> str:
            nums = []
            for u in usuarios:
                if (u.get("rango_usuario", "") or "").strip().lower() == "administrador":
                    continue
                s = str(u.get("ID_usuario", "") or "").strip()
                if s.isdigit():
                    nums.append(int(s))
            return str(max(nums) + 1) if nums else "1"

        def do_add():
            nombre = (t_nombre.value or "").strip()
            correo = (t_correo.value or "").strip()
            rango  = (dd_rango.value or "").strip()

            if not nombre or not correo:
                page.snack_bar = ft.SnackBar(ft.Text("Completá nombre y correo."))
                page.snack_bar.open = True; page.update(); return
            if "@" not in correo or "." not in correo.split("@")[-1]:
                page.snack_bar = ft.SnackBar(ft.Text("Correo inválido."))
                page.snack_bar.open = True; page.update(); return

            ID_usuario = _next_user_id()

            busy.visible = True
            btn_ok.disabled = True
            btn_cancel.disabled = True
            page.update()
            try:
                # 1) Guardar en la hoja 'usuarios'
                api.add(
                    ID_usuario=ID_usuario,
                    nombre_usuario=nombre,
                    correo_usuario=correo,
                    rango_usuario=rango
                )

                # 2) Intentar dar permiso en Drive (no bloquea si falla)
                try:
                    upsert_user_permission(page, sheet_id, correo, rango, send_email=True)
                except Exception as ex_perm:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Atención: permiso de Drive no creado/actualizado ({ex_perm})."))
                    page.snack_bar.open = True

                load_list()
                close_bs()
                page.snack_bar = ft.SnackBar(ft.Text("Usuario agregado."))
                page.snack_bar.open = True; page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {ex}"))
                page.snack_bar.open = True; page.update()
            finally:
                busy.visible = False
                btn_ok.disabled = False
                btn_cancel.disabled = False
                page.update()

        btn_ok.on_click = lambda e: do_add()
        btn_cancel.on_click = lambda e: close_bs()
        t_nombre.on_submit = lambda e: do_add()
        t_correo.on_submit = lambda e: do_add()
        page.update()

    # ---------------- Layout ----------------
    def copy_sheet_link(_=None):
        link = sheet_web_link(sheet_id)
        try:
            page.set_clipboard(link)
            page.snack_bar = ft.SnackBar(ft.Text("Link del Sheet copiado al portapapeles."))
        except Exception:
            page.snack_bar = ft.SnackBar(ft.Text(link))
        page.snack_bar.open = True; page.update()

    header_left = ft.Text("Usuarios", size=22, weight=ft.FontWeight.W_700)
    header_right = ft.Row(
        spacing=8,
        controls=[
            ft.OutlinedButton("Copiar link", icon=ft.Icons.LINK, on_click=copy_sheet_link),
            status,
        ],
    )
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[header_left, header_right],
    )

    btn_add = ft.FilledButton(
        "Agregar usuario",
        icon=ft.Icons.PERSON_ADD,
        on_click=open_add_user,
        style=ft.ButtonStyle(bgcolor=RED, color=WHITE),
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
                btn_add,
                ft.Container(expand=True, content=lv),
            ],
        ),
    )

    load_list()
    return root
