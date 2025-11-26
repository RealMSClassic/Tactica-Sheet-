# front/ventana_sheet_item_actions.py
from __future__ import annotations
import flet as ft

from back.sheets_ops import (
    update_index_name_by_sheet_id,
    clear_index_row_by_sheet_id,
    rename_file_in_drive,  # lo intentamos; si falla, seguimos igual
)

def open_rename_index_dialog(
    page: ft.Page,
    item: dict,                      # {"id", "name", ...}
    on_done: callable | None = None  # callback(item_actualizado)
):
    tf = ft.TextField(value=item.get("name", ""), label="Nuevo nombre", width=360, autofocus=True)
    btn_ok = ft.FilledButton("Guardar")
    btn_cancel = ft.OutlinedButton("Cancelar")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Renombrar sheet"),
        content=tf,
        actions=[btn_cancel, btn_ok],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def ok(_):
        new_name = (tf.value or "").strip()
        if not new_name:
            page.snack_bar = ft.SnackBar(ft.Text("Ingresá un nombre válido."))
            page.snack_bar.open = True; page.update()
            return
        try:
            index_id = page.client_storage.get("tactica_index_sheet_id")
            if not index_id:
                raise ValueError("No hay indexSheetList disponible.")

            # 1) actualizar el nombre en el índice
            updated = update_index_name_by_sheet_id(page, index_id, item["id"], new_name)
            if not updated:
                raise RuntimeError("No se encontró el sheet en el índice.")

            # 2) (opcional) renombrar en Drive también; si falla, no frenamos
            try:
                rename_file_in_drive(page, item["id"], new_name)
            except Exception:
                pass

            # 3) actualizar objeto y avisar al caller
            item["name"] = new_name
            if on_done:
                on_done(item)

            page.snack_bar = ft.SnackBar(ft.Text("Nombre actualizado."))
            page.snack_bar.open = True
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al renombrar: {ex}"))
            page.snack_bar.open = True
        finally:
            dlg.open = False
            page.update()

    btn_ok.on_click = ok
    btn_cancel.on_click = lambda e: (setattr(dlg, "open", False), page.update())

    page.dialog = dlg
    dlg.open = True
    page.update()


def open_delete_index_dialog(
    page: ft.Page,
    item: dict,                      # {"id", "name", "estado", ...}
    on_done: callable | None = None  # callback(item_eliminado)
):
    estado = (item.get("estado", "") or "").strip().lower()

    if estado in ("creador", "administrador"):
        title = "Eliminar (Creador)"
        msg = (
            f"Vas a eliminar '{item.get('name','')}' de tu lista.\n\n"
            "Como Creador, otras personas no podrán unirse más a este sheet.\n"
            "¿Estás seguro?"
        )
    elif estado == "invitado":
        title = "Eliminar (Invitado)"
        msg = f"¿Seguro que querés eliminar '{item.get('name','')}' de tu lista?"
    else:  # "no existe" u otro estado
        title = "Eliminar"
        msg = f"¿Seguro que querés eliminar '{item.get('name','')}' de tu lista?"

    btn_yes = ft.FilledButton("Eliminar")
    btn_no = ft.OutlinedButton("Cancelar")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=ft.Text(msg),
        actions=[btn_no, btn_yes],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def yes(_):
        try:
            index_id = page.client_storage.get("tactica_index_sheet_id")
            if not index_id:
                raise ValueError("No hay indexSheetList disponible.")

            ok = clear_index_row_by_sheet_id(page, index_id, item["id"])
            if not ok:
                raise RuntimeError("No se encontró la fila a eliminar en el índice.")

            if on_done:
                on_done(item)

            page.snack_bar = ft.SnackBar(ft.Text("Eliminado de tu lista."))
            page.snack_bar.open = True
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error al eliminar: {ex}"))
            page.snack_bar.open = True
        finally:
            dlg.open = False
            page.update()

    btn_yes.on_click = yes
    btn_no.on_click = lambda e: (setattr(dlg, "open", False), page.update())

    page.dialog = dlg
    dlg.open = True
    page.update()
