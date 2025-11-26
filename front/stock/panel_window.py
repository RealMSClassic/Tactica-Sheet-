# front/stock/panel_window.py
import flet as ft
import os, sys, importlib, importlib.util, traceback
import importlib

PRIMARY = "#E53935"
WHITE = ft.Colors.WHITE
BG = ft.Colors.GREY_50
TXT = ft.Colors.BLACK87
TXT_MUTED = ft.Colors.BLUE_GREY_600

# === Elegí el estilo de carga: "overlay" o "button" ===
LOADING_STYLE = "overlay"   # "overlay" | "button"

import types
if "back.sheet.gestor" not in sys.modules and "back.sheet.tabGestor" in sys.modules:
    sys.modules["back.sheet.gestor"] = sys.modules["back.sheet.tabGestor"]

# ====== Import de módulos ======
try:
    from front.stock.modules.stock import stock_view as stock_module_view
except Exception:
    stock_module_view = None

try:
    from front.stock.modules.deposito import depositos_view as deposito_module_view
except Exception:
    deposito_module_view = None

try:
    from front.stock.modules.items import items_view as items_module_view
except Exception:
    items_module_view = None

try:
    from front.stock.modules.usuarios import usuarios_view as usuarios_module_view
except Exception:
    usuarios_module_view = None

try:
    from front.stock.modules.log import log_view as logs_module_view
except Exception:
    logs_module_view = None


# ===== Util: cargar gestorMain por paquete o por ruta =====
def _load_gestor_view_callable():
    """
    Intenta obtener una función de vista desde:
      1) back.sheet.tabGestor.gestorMain (si el paquete está correcto)
      2) la ruta ./back/sheet/tabGestor/gestorMain.py (carga por archivo)
    Devuelve (callable | None, error_str | None)
    """
    # 1) Import por paquete
    try:
        mod = importlib.import_module("back.sheet.tabGestor.gestorMain")
        for name in ("gestor_view", "gestorMain_view", "view", "main_view", "panel_view", "gestorMain"):
            fn = getattr(mod, name, None)
            if callable(fn):
                return fn, None
        return None, "No se encontró una función exportada en gestorMain.py (probá: gestor_view, gestorMain_view, view, main_view, panel_view, gestorMain)."
    except Exception as e_pkg:
        pkg_err = f"[import paquete] {e_pkg}"

    # 2) Import por ruta de archivo
    try:
        base_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
        gestor_path = os.path.join(project_root, "back", "sheet", "tabGestor", "gestorMain.py")
        if not os.path.isfile(gestor_path):
            return None, f"No existe el archivo en ruta esperada: {gestor_path}"

        spec = importlib.util.spec_from_file_location("gestorMain_dyn", gestor_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["gestorMain_dyn"] = mod
        assert spec and spec.loader
        spec.loader.exec_module(mod)

        for name in ("gestor_view", "gestorMain_view", "view", "main_view", "panel_view", "gestorMain"):
            fn = getattr(mod, name, None)
            if callable(fn):
                return fn, None
        return None, "El archivo se cargó, pero no exporta una función de vista conocida."
    except Exception as e_fs:
        tb = traceback.format_exc(limit=2)
        return None, f"[import ruta] {e_fs}\n{tb}"


# cache para no re-importar cada vez
_GESTOR_VIEW_FN = None
_GESTOR_ERR = None
def _get_gestor_view():
    global _GESTOR_VIEW_FN, _GESTOR_ERR
    if _GESTOR_VIEW_FN or _GESTOR_ERR:
        return _GESTOR_VIEW_FN, _GESTOR_ERR
    _GESTOR_VIEW_FN, _GESTOR_ERR = _load_gestor_view_callable()
    return _GESTOR_VIEW_FN, _GESTOR_ERR


def panel_window_view(page: ft.Page) -> ft.View:
    # Contexto de la base
    sheet_name = (
        page.session.get("sheet_name")
        or page.client_storage.get("active_sheet_name")
        or "-"
    )
    sheet_id = (
        page.session.get("sheet_id")
        or page.client_storage.get("active_sheet_id")
        or ""
    )
    if not sheet_id:
        page.go("/sheets")
        return ft.View(route="/panel_window", controls=[])

    # Re-sync mínimos
    if page.session.get("sheet_id") != sheet_id:
        page.session.set("sheet_id", sheet_id)
    if page.client_storage.get("active_sheet_id") != sheet_id:
        page.client_storage.set("active_sheet_id", sheet_id)
    if page.session.get("sheet_name") != sheet_name:
        page.session.set("sheet_name", sheet_name)
    if page.client_storage.get("active_sheet_name") != sheet_name:
        page.client_storage.set("active_sheet_name", sheet_name)

    # Refuerzo para backends que leen page.app_ctx
    if not hasattr(page, "app_ctx") or not isinstance(page.app_ctx, dict):
        page.app_ctx = {}
    page.app_ctx["sheet"] = {"id": sheet_id, "name": sheet_name}

    # ===== Estado =====
    sidebar_open = False
    is_loading = {"value": False}
    selected_key = page.session.get("panel_selected") or "gestor"
    # Si quedó una clave obsoleta (stock/deposito/items), forzamos Gestor
    if selected_key in {"stock", "deposito", "items"}:
        selected_key = "gestor"
        page.session.set("panel_selected", selected_key)

    # ===== Estilos =====
    normal_style = ft.ButtonStyle(
        bgcolor=ft.Colors.TRANSPARENT,
        color=TXT,
        overlay_color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
        padding=ft.padding.symmetric(horizontal=14, vertical=10),
        shape=ft.RoundedRectangleBorder(radius=10),
        animation_duration=200,
    )
    selected_style = ft.ButtonStyle(
        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
        color=TXT,
        padding=ft.padding.symmetric(horizontal=14, vertical=10),
        shape=ft.RoundedRectangleBorder(radius=10),
        animation_duration=200,
    )

    # ===== Vistas =====
    def card_stub(title: str, desc: str) -> ft.Control:
        return ft.Container(
            bgcolor=WHITE,
            border_radius=12,
            padding=16,
            shadow=ft.BoxShadow(blur_radius=4, color=ft.Colors.GREY_200, spread_radius=0.5),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Text(title, size=18, weight=ft.FontWeight.W_700, color=TXT),
                    ft.Text(desc, size=13, color=TXT_MUTED),
                    ft.Divider(height=1, color=ft.Colors.GREY_200),
                    ft.Text("Módulo no disponible.", size=12, color=ft.Colors.GREY_600),
                ],
            ),
        )

    def error_card(title: str, err: str) -> ft.Control:
        return ft.Container(
            bgcolor=WHITE,
            border_radius=12,
            padding=16,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Text(title, size=18, weight=ft.FontWeight.W_700, color=TXT),
                    ft.Text("Se produjo un error al cargar el módulo:", size=13, color=ft.Colors.RED),
                    ft.Text(err, size=12, color=ft.Colors.GREY_700, selectable=True),
                ],
            ),
        )

    def view_home() -> ft.Control:
        return ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Panel principal", size=24, weight=ft.FontWeight.W_700, color=TXT),
                ft.Container(height=8),
                ft.Text(f"Base: {sheet_name}", size=16, color=TXT_MUTED),
            ],
        )

    # Estas vistas pueden quedar, pero ya no hay botones de menú para ellas
    def view_stock() -> ft.Control:
        return card_stub("Stock", "Gestión de stock")

    def view_deposito() -> ft.Control:
        return card_stub("Depósito", "Gestión de depósitos")

    def view_items() -> ft.Control:
        return card_stub("Items", "ABM de items")

    def view_usuarios() -> ft.Control:
        return usuarios_module_view(page) if callable(usuarios_module_view) else card_stub("Usuarios", "Gestión de usuarios")

    def view_logs() -> ft.Control:
        return logs_module_view(page) if callable(logs_module_view) else card_stub("Logs", "Eventos y auditoría")

    def view_gestor() -> ft.Control:
        fn, err = _get_gestor_view()
        if err:
            return error_card("Gestor", err)
        try:
            view_ctrl = fn(page)
            if not isinstance(view_ctrl, ft.Control):
                return error_card("Gestor", "La función retornó un objeto que no es ft.Control.")
            return view_ctrl
        except Exception as e:
            tb = traceback.format_exc(limit=2)
            return error_card("Gestor", f"{e}\n{tb}")

    def get_view(key: str | None) -> ft.Control:
        # Redirigir cualquier clave obsoleta a Gestor
        if key in {"stock", "deposito", "items"}:
            return view_gestor()
        if key == "usuario":
            return view_usuarios()
        if key == "logs":
            return view_logs()
        if key == "gestor":
            return view_gestor()
        return view_home()

    # --- ClientStorage snapshot/patch helpers para evitar timeouts en run_task ---
    _cs_orig_get = {"fn": None}
    _cs_snapshot = {"data": None}

    def _session_get_no_default(page: ft.Page, key: str, default=None):
        """
        Flet SessionStorage.get(key) NO acepta default → no pasar segundo argumento.
        """
        try:
            v = page.session.get(key)
        except Exception:
            v = None
        return v if v is not None else default

    def _make_cs_snapshot(page: ft.Page) -> dict:
        """
        Arma un snapshot priorizando session; si no está, intenta client_storage.
        (Se llama SIEMPRE en el main thread, antes de run_task).
        """
        keys = ("active_sheet_id", "active_sheet_name", "user_name", "user_email", "user_uid")
        snap = {}
        for k in keys:
            v = _session_get_no_default(page, k, None)
            if v is None:
                try:
                    v = page.client_storage.get(k)
                except Exception:
                    v = None
            snap[k] = v
        return snap

    def _patch_client_storage_for_task(page: ft.Page, enable: bool, *, preloaded: dict | None = None):
        """
        enable=True: reemplaza page.client_storage.get por una versión que lee del snapshot.
        enable=False: restaura el .get original.
        """
        if enable:
            if _cs_orig_get["fn"] is None:
                _cs_orig_get["fn"] = page.client_storage.get
                _cs_snapshot["data"] = preloaded if preloaded is not None else _make_cs_snapshot(page)

                def _fake_get(key: str, default=None):
                    data = _cs_snapshot["data"] or {}
                    return data.get(key, default)

                page.client_storage.get = _fake_get
        else:
            if _cs_orig_get["fn"] is not None:
                page.client_storage.get = _cs_orig_get["fn"]
                _cs_orig_get["fn"] = None
                _cs_snapshot["data"] = None

    # ===== Helpers =====
    def wrap_content(inner: ft.Control) -> ft.Control:
        return ft.Container(
            expand=True, bgcolor=BG, padding=20,
            content=ft.Container(expand=True, alignment=ft.alignment.top_left, content=inner),
        )

    def toggle_sidebar(_=None):
        nonlocal sidebar_open
        if is_loading["value"]:
            return
        sidebar_open = not sidebar_open
        sidebar.width = 240 if sidebar_open else 0
        sidebar.visible = True
        page.update()

    # === Loading overlays / button spinners ===
    loading_overlay = ft.Container(
        visible=False,
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
        alignment=ft.alignment.center,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(),
                ft.Container(height=10),
                ft.Text("Cargando…", size=18, color=WHITE),
            ],
        ),
    )

    # ===== Menú lateral =====
    # *** Gestor arriba de todo ***
    btn_gestor_ring = ft.ProgressRing(visible=False, width=14, height=14, stroke_width=2)
    btn_gestor = ft.TextButton(
        content=ft.Row(
            spacing=10,
            controls=[ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED), ft.Text("Gestor"), btn_gestor_ring],
        ),
        style=normal_style, on_click=lambda e: set_selected("gestor"),
    )

    btn_usuario_ring = ft.ProgressRing(visible=False, width=14, height=14, stroke_width=2)
    btn_usuario = ft.TextButton(
        content=ft.Row(spacing=10, controls=[ft.Icon(ft.Icons.PERSON_OUTLINE), ft.Text("Usuario"), btn_usuario_ring]),
        style=normal_style, on_click=lambda e: set_selected("usuario"),
    )

    btn_logs_ring = ft.ProgressRing(visible=False, width=14, height=14, stroke_width=2)
    btn_logs = ft.TextButton(
        content=ft.Row(spacing=10, controls=[ft.Icon(ft.Icons.HISTORY), ft.Text("Logs"), btn_logs_ring]),
        style=normal_style, on_click=lambda e: set_selected("logs"),
    )

    # Para habilitar/deshabilitar rápido
    menu_btn = ft.IconButton(ft.Icons.MENU, on_click=toggle_sidebar)
    btn_salir = ft.FilledButton(
        "Salir", icon=ft.Icons.LOGOUT,
        style=ft.ButtonStyle(bgcolor=WHITE, color=PRIMARY, shape=ft.RoundedRectangleBorder(radius=10)),
    )

    def set_menu_enabled(enabled: bool):
        btn_gestor.disabled = not enabled
        btn_usuario.disabled = not enabled
        btn_logs.disabled = not enabled
        btn_salir.disabled = not enabled
        menu_btn.disabled = not enabled

    def set_button_loading(key: str, loading: bool):
        # solo visible en modo "button"
        if LOADING_STYLE != "button":
            btn_gestor_ring.visible = False
            btn_usuario_ring.visible = False
            btn_logs_ring.visible = False
            return
        rings = {
            "gestor": btn_gestor_ring,
            "usuario": btn_usuario_ring,
            "logs": btn_logs_ring,
        }
        for k, ring in rings.items():
            ring.visible = (loading and k == key)

    # ===== Botón Salir con overlay =====
    fs_overlay = ft.Container(
        visible=False,
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.65, ft.Colors.BLACK),
        alignment=ft.alignment.center,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(),
                ft.Container(height=12),
                ft.Text("Saliendo…", size=18, color=WHITE),
            ],
        ),
    )

    def on_exit(_):
        if is_loading["value"]:
            return
        fs_overlay.visible = True
        page.update()

        async def _exit_flow():
            import asyncio
            for k in ("sheet_id", "sheet_name", "last_sheet_id", "panel_selected"):
                page.session.set(k, None)
            try:
                page.client_storage.remove("active_sheet_id")
                page.client_storage.remove("active_sheet_name")
            except Exception:
                pass
            await asyncio.sleep(0.8)
            page.go("/sheets")

        page.run_task(_exit_flow)

    btn_salir.on_click = on_exit

    sidebar = ft.Container(
        width=0,  # arranca cerrado
        visible=True,
        bgcolor=WHITE,
        padding=16,
        animate=ft.Animation(200, "easeInOut"),
        content=ft.Column(
            spacing=8, expand=True, controls=[
                ft.Text("Menú", size=16, weight=ft.FontWeight.W_700, color=TXT),
                ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_200),
                # Orden nuevo: Gestor primero
                btn_gestor,
                btn_usuario,
                btn_logs,
                ft.Container(expand=True),
                btn_salir,
            ],
        ),
    )

    content_holder = ft.Container(expand=True)
    body = ft.Row(expand=True, controls=[sidebar, content_holder])

    appbar = ft.AppBar(
        leading=menu_btn,
        title=ft.Text(f"Base : {sheet_name}", color=WHITE),
        center_title=False, bgcolor=PRIMARY, color=WHITE,
    )

    # Orden en el stack: body -> loading_overlay -> fs_overlay (Salir)
    stack = ft.Stack(expand=True, controls=[body, loading_overlay, fs_overlay])

    def highlight_menu():
        # Solo quedan: Gestor, Usuarios y Logs
        btn_gestor.style   = selected_style if selected_key == "gestor"   else normal_style
        btn_usuario.style  = selected_style if selected_key == "usuario"  else normal_style
        btn_logs.style     = selected_style if selected_key == "logs"     else normal_style

    def _show_loading(key: str):
        is_loading["value"] = True
        set_menu_enabled(False)
        if LOADING_STYLE == "overlay":
            loading_overlay.visible = True
        set_button_loading(key, True)
        page.update()

    def _hide_loading():
        is_loading["value"] = False
        set_menu_enabled(True)
        loading_overlay.visible = False
        set_button_loading("", False)
        page.update()

    def set_selected(key: str):
        nonlocal selected_key, sidebar_open
        if is_loading["value"]:
            return
        selected_key = key
        page.session.set("panel_selected", key)
        highlight_menu()
        # cerrar sidebar al seleccionar
        sidebar_open = False
        sidebar.width = 0
        sidebar.visible = True

        _show_loading(key)

        # Snapshot ANTES del task (main thread)
        snapshot = _make_cs_snapshot(page)

        async def _switch():
            import asyncio
            try:
                # Parcheamos client_storage.get para evitar timeouts dentro del task
                _patch_client_storage_for_task(page, True, preloaded=snapshot)

                # pequeña espera para que el overlay se pinte
                await asyncio.sleep(0)

                ctrl = get_view(selected_key)  # no invoca clientStorage del lado cliente
                content_holder.content = wrap_content(ctrl)
            except Exception as e:
                tb = traceback.format_exc(limit=2)
                content_holder.content = wrap_content(error_card("Error", f"{e}\n{tb}"))
            finally:
                # Restauramos el client_storage.get original y ocultamos loading
                _patch_client_storage_for_task(page, False)
                _hide_loading()

        page.run_task(_switch)

    # Render inicial
    def first_render():
        highlight_menu()
        content_holder.content = wrap_content(get_view(selected_key))
        page.update()
    first_render()

    return ft.View(route="/panel_window", appbar=appbar, controls=[stack])
