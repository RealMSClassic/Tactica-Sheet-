# front/ventana_sheet_add.py
import flet as ft
from datetime import datetime

def sheet_add_dialog(page: ft.Page, on_created=None) -> ft.AlertDialog:
    tf = ft.TextField(label="Nombre del Sheet", width=380, autofocus=True)
    btn_cancel = ft.OutlinedButton("Cancelar")
    btn_ok = ft.FilledButton("Crear")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Nuevo Sheet"),
        content=ft.Column([tf], tight=True),
        actions=[btn_cancel, btn_ok],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def close(_=None):
        dlg.open = False
        page.update()

    def do_ok(_):
        name = (tf.value or "").strip()
        if not name:
            page.snack_bar = ft.SnackBar(ft.Text("Ingresá un nombre."))
            page.snack_bar.open = True
            page.update()
            return
        # ← aquí iría tu lógica real de crear el sheet y escribir en index
        # demo:
        new_item = {
            "name": name,
            "id": "demo_id",
            "created": datetime.now().strftime("%d/%m/%Y"),
        }
        if on_created:
            on_created(new_item)
        close()

    btn_ok.on_click = do_ok
    btn_cancel.on_click = close
    return dlg
