import flet as ft
import inspect

# Intentamos ubicar tu pantalla de Stock; ajusta si tu nombre/folder cambia.
try:
    from front.stock.ventana_stock import stock_view as stock_screen
except Exception:
    try:
        from front.stock.ventana_stock import stock_view as stock_screen
    except Exception:
        stock_screen = None


def panel_shell_window_view(page: ft.Page) -> ft.View:
    # 1) Verificar que haya un sheet seleccionado
    sheet_id = page.session.get("sheet_id") or page.client_storage.get("active_sheet_id")
    sheet_name = page.session.get("sheet_name") or page.client_storage.get("active_sheet_name") or ""
    if not sheet_id:
        page.go("/sheets")
        return ft.View(route="/panel_window", controls=[
            ft.Container(expand=True, alignment=ft.alignment.center,
                         content=ft.Text("Elegí un Sheet para continuar…"))
        ])

    # 2) Definir módulos del panel
    modules = {
        "stock": {
            "label": "Stock",
            "icon": ft.Icons.INVENTORY_2_OUTLINED,
            "builder": stock_screen,  # puede devolver View o Control
        },
        # Podés agregar más módulos aquí...
    }

    selected_key = page.session.get("panel_selected") or "stock"
    if selected_key not in modules:
        selected_key = "stock"

    # ---------- utilidades para normalizar builder ----------
    def _normalize_to_control(result: ft.Control) -> ft.Control:
        # Si el módulo devolvió un View, lo hacemos embebible
        if isinstance(result, ft.View):
            return ft.Container(expand=True, content=ft.Column(expand=True, controls=result.controls))
        if isinstance(result, ft.Control):
            return result
        return ft.Text("Módulo sin contenido", color=ft.Colors.RED)

    def _call_builder(builder):
        if builder is None:
            return ft.Text("Módulo no disponible", color=ft.Colors.RED)
        try:
            sig = inspect.signature(builder)
            if len(sig.parameters) >= 2:
                return builder(page, sheet_id)
            return builder(page)
        except TypeError:
            try:
                return builder(page)
            except Exception as e:
                return ft.Text(f"Error al instanciar módulo: {e}", color=ft.Colors.RED)
        except Exception as e:
            return ft.Text(f"Error al instanciar módulo: {e}", color=ft.Colors.RED)

    def render_module(key: str) -> ft.Control:
        return _normalize_to_control(_call_builder(modules[key]["builder"]))

    content_holder = ft.Container(expand=True, content=render_module(selected_key))

    # ---------- navegación lateral ----------
    def on_nav_change(e: ft.ControlEvent):
        idx = e.control.selected_index
        key = list(modules.keys())[idx]
        page.session.set("panel_selected", key)
        content_holder.content = render_module(key)
        page.update()

    destinations = [
        ft.NavigationRailDestination(icon=m["icon"], label=m["label"])
        for m in modules.values()
    ]
    selected_index = list(modules.keys()).index(selected_key)

    rail = ft.NavigationRail(
        selected_index=selected_index,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=64,
        min_extended_width=160,
        extended=False,
        on_change=on_nav_change,
        destinations=destinations,
    )

    body = ft.Row(
        expand=True,
        controls=[
            ft.Container(width=80, content=rail),
            content_holder,
        ],
    )

    # ---------- botón Salir (sin botón de “volver”) ----------
    def on_exit(_):
        # limpiar selección del sheet y volver a lista
        for k in ("sheet_id", "sheet_name", "last_sheet_id", "panel_selected"):
            page.session.set(k, None)
        try:
            page.client_storage.remove("active_sheet_id")
            page.client_storage.remove("active_sheet_name")
        except Exception:
            pass
        page.go("/sheets")

    appbar = ft.AppBar(
        # Sin leading/back
        title=ft.Text(f"Panel — {sheet_name}" if sheet_name else "Panel"),
        center_title=False,
        bgcolor="#E53935",
        color=ft.Colors.WHITE,
        actions=[
            ft.FilledButton(
                "Salir",
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.WHITE,
                    color="#E53935",
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                on_click=on_exit,
            )
        ],
    )

    return ft.View(route="/panel_window", appbar=appbar, controls=[body])
