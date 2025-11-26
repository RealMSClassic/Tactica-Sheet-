# front/stock/modules/log.py
import flet as ft
from typing import List, Dict
from back.drive.drive_check import build_sheets_service
from datetime import datetime

RED = "#E53935"
WHITE = ft.Colors.WHITE
BG = ft.Colors.GREY_50
LOG_SHEET = "logs"   # columnas: data_ini_prox | fecha | ID_usuario | Accion


def log_view(page: ft.Page) -> ft.Control:
    # Sheet activo
    sheet_id = (
        page.client_storage.get("active_sheet_id")
        or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
    )
    if not sheet_id:
        return ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=ft.Text("Elegí un Sheet para ver el log.", size=18, color=ft.Colors.RED),
        )

    svc = build_sheets_service(page)

    # Estado
    logs: List[Dict] = []       # [{"fecha": str, "responsable": str, "accion": str}, ...]
    filtered: List[Dict] = []

    # sort_mode: 'date_asc' | 'date_desc' | 'resp_asc' | 'resp_desc'
    sort_mode = {"value": "date_desc"}

    status_txt = ft.Text("", size=12, color=ft.Colors.GREY_600)

    search = ft.TextField(
        hint_text="Buscar por acción...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=WHITE,
        border_radius=12,
        border_color=RED,
        focused_border_color=RED,
        content_padding=10,
        on_change=lambda _: _apply_filter_and_sort(),
        expand=True,
    )

    sort_btn = ft.PopupMenuButton(
        icon=ft.Icons.FILTER_LIST,
        tooltip="Ordenar",
        items=[
            ft.PopupMenuItem(text="Fecha ↑ (más viejo primero)", on_click=lambda _: _set_sort("date_asc")),
            ft.PopupMenuItem(text="Fecha ↓ (más reciente primero)", on_click=lambda _: _set_sort("date_desc")),
            ft.PopupMenuItem(),  # divider
            ft.PopupMenuItem(text="Responsable A–Z", on_click=lambda _: _set_sort("resp_asc")),
            ft.PopupMenuItem(text="Responsable Z–A", on_click=lambda _: _set_sort("resp_desc")),
        ],
    )

    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Fecha")),
            ft.DataColumn(ft.Text("Responsable")),
            ft.DataColumn(ft.Text("Acción")),
        ],
        rows=[],
        heading_row_color=ft.Colors.GREY_100,
        data_row_min_height=44,
        horizontal_margin=12,
        column_spacing=24,
        divider_thickness=0.5,
        show_checkbox_column=False,
    )

    def _parse_date(s: str):
        """Devuelve (timestamp, texto_normalizado) para ordenar de forma robusta."""
        s = (s or "").strip()
        # Try varios formatos comunes
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.timestamp(), s
            except Exception:
                continue
        # Si no parsea, lo empujamos al final/ principio según orden usando None
        return None, s

    def _read_logs() -> List[Dict]:
        """
        Lee logs!B2:D (B: fecha, C: ID_usuario, D: Accion)
        y devuelve lista con fecha/responsable/accion.
        """
        try:
            resp = svc.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=f"{LOG_SHEET}!B2:D",
            ).execute()
            rows = resp.get("values", []) or []
            out: List[Dict] = []
            for r in rows:
                # r = [fecha, id_usuario, accion]
                fecha = (r[0].strip() if len(r) > 0 else "")
                responsable = (r[1].strip() if len(r) > 1 else "")
                accion = (r[2].strip() if len(r) > 2 else "")
                if fecha or responsable or accion:
                    out.append({"fecha": fecha, "responsable": responsable, "accion": accion})
            return out
        except Exception as ex:
            # Si la hoja no existe o hay error, mostramos vacío y el estado indica error
            status_txt.value = f"No se pudo leer '{LOG_SHEET}': {ex}"
            page.update()
            return []

    def _refresh_table():
        table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(r.get("fecha", ""))),
                    ft.DataCell(ft.Text(r.get("responsable", ""))),
                    ft.DataCell(ft.Text(r.get("accion", ""))),
                ]
            )
            for r in filtered
        ]
        status_txt.value = f"Registros: {len(logs)} | Filtrados: {len(filtered)}"
        page.update()

    def _apply_filter_and_sort():
        # filtro por acción
        q = (search.value or "").strip().lower()
        filtered.clear()
        if not q:
            filtered.extend(logs)
        else:
            filtered.extend([r for r in logs if q in (r.get("accion", "").lower())])

        # sort
        mode = sort_mode["value"]
        if mode.startswith("date_"):
            # Orden por fecha usando timestamp; None va al final en asc y al principio en desc
            with_keys = []
            for r in filtered:
                ts, _ = _parse_date(r.get("fecha", ""))
                with_keys.append((ts, r))
            if mode == "date_asc":
                with_keys.sort(key=lambda t: (t[0] is None, t[0]))
            else:  # date_desc
                with_keys.sort(key=lambda t: (t[0] is None, -(t[0] or 0)))
            filtered[:] = [r for _, r in with_keys]
        else:
            key = (lambda r: (r.get("responsable", "") or "").lower())
            reverse = (mode == "resp_desc")
            filtered.sort(key=key, reverse=reverse)

        _refresh_table()

    def _set_sort(mode: str):
        sort_mode["value"] = mode
        _apply_filter_and_sort()

    # Layout
    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Log", size=22, weight=ft.FontWeight.W_700),
            status_txt,
        ],
    )
    search_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=8,
        controls=[search, sort_btn],
    )

    root = ft.Container(
        bgcolor=WHITE,
        expand=True,
        border_radius=12,
        padding=20,
        content=ft.Column(
            expand=True,
            spacing=12,
            controls=[
                header_row,
                search_row,
                ft.Container(
                    expand=True,
                    bgcolor=BG,
                    border_radius=10,
                    padding=8,
                    content=ft.ListView(expand=True, controls=[table]),
                ),
            ],
        ),
    )

    # Carga inicial
    logs[:] = _read_logs()
    filtered[:] = list(logs)
    _apply_filter_and_sort()

    return root
