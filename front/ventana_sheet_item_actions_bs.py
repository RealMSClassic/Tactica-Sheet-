# front/ventana_sheet_item_actions_bs.py
import flet as ft
from back.sheets_ops import (
    update_index_name_by_sheet_id,
    clear_index_row_by_sheet_id,
)

# ---- Renombrar (BottomSheet) ----
def open_rename_index_bs(page: ft.Page, item: dict, on_done=None):
    tf = ft.TextField(
        value=item.get("name", ""),
        label="Nuevo nombre",
        autofocus=True,
        width=420,
        border_radius=12,
        filled=True,
        bgcolor=ft.Colors.WHITE,
    )

    btn_cancel = ft.OutlinedButton("Cancelar")
    btn_ok = ft.FilledButton(
        "Guardar",
        icon=ft.Icons.CHECK,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE
        ),
    )

    content = ft.Container(
        padding=ft.padding.all(16),
        bgcolor=ft.Colors.WHITE,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("Renombrar sheet", size=18, weight=ft.FontWeight.W_600),
                tf,
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_ok]),
            ],
        ),
    )

    bs = ft.BottomSheet(
        content=content,
        show_drag_handle=True,
        is_scroll_controlled=False,
        on_dismiss=lambda e: page.update(),
    )

    def close(_=None):
        try:
            page.close(bs)
        except Exception:
            bs.open = False
            page.update()

    def do_ok(_):
        new_name = (tf.value or "").strip()
        if not new_name:
            page.snack_bar = ft.SnackBar(ft.Text("Ingresá un nombre válido."))
            page.snack_bar.open = True; page.update()
            return

        index_id = page.client_storage.get("tactica_index_sheet_id")
        if not index_id:
            page.snack_bar = ft.SnackBar(ft.Text("No hay índice disponible."))
            page.snack_bar.open = True; page.update()
            return

        try:
            update_index_name_by_sheet_id(page, index_id, item["id"], new_name)
            if on_done:
                on_done({"id": item["id"], "name": new_name})
            close()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al renombrar: {ex}"))
            page.snack_bar.open = True; page.update()

    btn_ok.on_click = do_ok
    btn_cancel.on_click = close
    page.open(bs)


# ---- Eliminar (BottomSheet) ----
def open_delete_index_bs(page: ft.Page, item: dict, on_done=None):
    estado = (item.get("estado", "") or "").strip().lower()
    if estado in ("creador", "administrador"):
        title_text = "Eliminar como Creador"
        body_text = (
            "Vas a quitar este sheet de tu índice. "
            "Si sos Creador, otras personas ya no podrán unirse desde tu lista. ¿Continuar?"
        )
    else:
        title_text = "Eliminar acceso"
        body_text = "Vas a quitar este sheet de tu lista. ¿Confirmás?"

    btn_cancel = ft.OutlinedButton("Cancelar")
    btn_yes = ft.FilledButton(
        "Eliminar",
        icon=ft.Icons.DELETE,
        style=ft.ButtonStyle(bgcolor=ft.Colors.RED, color=ft.Colors.WHITE),
    )

    content = ft.Container(
        padding=ft.padding.all(16),
        bgcolor=ft.Colors.WHITE,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text(title_text, size=18, weight=ft.FontWeight.W_600),
                ft.Text(body_text),
                ft.Row(alignment=ft.MainAxisAlignment.END, controls=[btn_cancel, btn_yes]),
            ],
        ),
    )

    bs = ft.BottomSheet(
        content=content,
        show_drag_handle=True,
        is_scroll_controlled=False,
        on_dismiss=lambda e: page.update(),
    )

    def close(_=None):
        try:
            page.close(bs)
        except Exception:
            bs.open = False
            page.update()

    def do_yes(_):
        index_id = page.client_storage.get("tactica_index_sheet_id")
        if not index_id:
            page.snack_bar = ft.SnackBar(ft.Text("No hay índice disponible."))
            page.snack_bar.open = True; page.update()
            return

        try:
            # Solo quitamos la fila del índice (NO se manda a la papelera de Drive)
            clear_index_row_by_sheet_id(page, index_id, item["id"])
            if on_done:
                on_done({"id": item["id"]})
            close()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al eliminar: {ex}"))
            page.snack_bar.open = True; page.update()

    btn_yes.on_click = do_yes
    btn_cancel.on_click = close
    page.open(bs)
