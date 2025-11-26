# ./back/sheet/tabGestor/tabItems/listaItems.py
from __future__ import annotations
import flet as ft

ROW_HEIGHT = 96
ROW_SPACING = 8
MAX_ROWS_VISIBLE = 7

def calc_height(n_rows: int) -> int:
    if n_rows <= 0:
        return ROW_HEIGHT
    vis = min(n_rows, MAX_ROWS_VISIBLE)
    return vis * ROW_HEIGHT + (vis - 1) * ROW_SPACING

# Requiere: backend.filter, search_value (str), sort_mode (str), open_edit_panel (callback)
# Campos: codigo_producto, nombre_producto, descripcion_producto, RecID_imagen/imagen_url

def crear_lista_items(backend, search_value, sort_mode, open_edit_panel):
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)
    lv = ft.ListView(spacing=ROW_SPACING, auto_scroll=False)

    q = (search_value or "").strip()
    rows = backend.filter(q)

    def key_name(r): return (r.get("nombre_producto") or "").lower()
    def key_id(r):   return (r.get("codigo_producto") or "").lower()

    if sort_mode == "name_asc":
        rows = sorted(rows, key=key_name)
    elif sort_mode == "name_desc":
        rows = sorted(rows, key=key_name, reverse=True)
    elif sort_mode == "id_asc":
        rows = sorted(rows, key=key_id)
    elif sort_mode == "id_desc":
        rows = sorted(rows, key=key_id, reverse=True)

    for r in rows:
        nombre = r.get("nombre_producto", "") or "(sin nombre)"
        codigo = r.get("codigo_producto", "") or "-"
        descr  = r.get("descripcion_producto", "") or ""
        recid_imagen = (r.get("imagen_url") or r.get("RecID_imagen") or r.get("ID_Imagen") or "").strip()

        def on_click_row(_=None, recid=r.get("RecID", "")):
            open_edit_panel(recid)

        if recid_imagen and isinstance(recid_imagen, str) and recid_imagen.startswith(("http", "data:")):
            imagen_src = recid_imagen
        else:
            imagen_src = (
                "data:image/png;base64,"
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
            )

        imagen_placeholder = ft.Image(src=imagen_src, width=64, height=64, fit=ft.ImageFit.COVER, border_radius=8)

        texto_col = ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(nombre, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK87),
                        ft.Text(codigo, size=12, color=ft.Colors.GREY_700),
                    ],
                ),
                ft.Text(descr, size=11, color=ft.Colors.GREY_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ],
        )

        lv.controls.append(
            ft.Container(
                on_click=on_click_row,
                ink=True,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                padding=12,
                data={"recid_imagen": recid_imagen, "img_control": imagen_placeholder},
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        imagen_placeholder,
                        ft.Container(expand=True, content=texto_col),
                    ],
                ),
            )
        )

    status.value = f"Ítems: {len(rows)}"
    lv_holder = ft.Container(height=calc_height(len(rows)), content=lv)
    return lv_holder, status