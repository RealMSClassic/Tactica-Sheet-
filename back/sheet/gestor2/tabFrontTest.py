# ./back/sheet/gestor/tabFrontTest.py
import flet as ft
import base64, re, urllib.request, asyncio

PRIMARY = "#0066FF"
CARD_BORDER = ft.Colors.DEEP_ORANGE_300
WHITE = ft.Colors.WHITE

# Imagen A (inicial)
DRIVE_URL_A = "https://drive.google.com/file/d/1ImspR9wHjSlV85hty1P5-zImDpBr7oC9/view"

# PNG 1x1 transparente como placeholder
PLACEHOLDER_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="


# ---------- helpers ----------
def extract_drive_id(url_or_id: str) -> str:
    m = re.search(r"/d/([^/]+)/", url_or_id or "")
    return m.group(1) if m else (url_or_id or "").strip()

def drive_download_url(fid: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={fid}"

def fetch_bytes_from_drive_sync(fid: str) -> bytes | None:
    url = drive_download_url(fid)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            b = resp.read()
        return b
    except Exception as ex:
        print(f"[fetch] ERROR id={fid} ex={ex}", flush=True)
        return None

def guess_mime_from_bytes(b: bytes) -> str:
    if not b or len(b) < 12: return "image/jpeg"
    if b.startswith(b"\xff\xd8"): return "image/jpeg"
    if b.startswith(b"\x89PNG"):  return "image/png"
    if b.startswith(b"GIF8"):     return "image/gif"
    if b[:4]==b"RIFF" and b[8:12]==b"WEBP": return "image/webp"
    return "image/jpeg"

def to_b64(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def make_data_url(b: bytes) -> str:
    return f"data:{guess_mime_from_bytes(b)};base64,{to_b64(b)}"

def safe_update(ctrl: ft.Control):
    try:
        if getattr(ctrl, "page", None):
            ctrl.update()
    except Exception as ex:
        print(f"[safe_update] skip: {ex}", flush=True)

def _image_box(img_ctrl: ft.Image):
    return ft.Container(
        width=200, height=200,
        bgcolor=ft.Colors.WHITE,
        border=ft.border.all(3, CARD_BORDER),
        border_radius=24,
        shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.GREY_400, spread_radius=0, offset=ft.Offset(1,2)),
        alignment=ft.alignment.center,
        content=img_ctrl,
    )


# ---------- tab principal ----------
def build_test_tab(page: ft.Page, backend=None, bus=None) -> ft.Control:
    """
    Un solo cuadro (data-URL). Carga A automáticamente.
    Click en el cuadro => panel con imagen grande.
    """

    # estado local de la imagen (guardamos el data-url para reutilizar)
    state = {"data_url": f"data:image/png;base64,{PLACEHOLDER_B64}"}

    # miniatura
    img_small = ft.Image(
        width=180, height=180,
        fit=ft.ImageFit.CONTAIN,
        src=state["data_url"],
        error_content=ft.Text("error", color=ft.Colors.GREY_600, size=12),
    )

    # loader asíncrono (data-url)
    async def load_data_url_async(url_or_id: str):
        fid = extract_drive_id(url_or_id)
        print(f"[data-url] START id={fid}", flush=True)
        b = await asyncio.to_thread(fetch_bytes_from_drive_sync, fid)
        if not b:
            print(f"[data-url] FAIL id={fid}", flush=True)
            state["data_url"] = f"data:image/png;base64,{PLACEHOLDER_B64}"
            img_small.src = state["data_url"]
            safe_update(img_small); return
        state["data_url"] = make_data_url(b)
        img_small.src = state["data_url"]
        print(f"[data-url] DONE id={fid} bytes={len(b)}", flush=True)
        safe_update(img_small)

    # click => panel grande
    def open_big_panel(_=None):
        big_img = ft.Image(
            src=state["data_url"],
            width=500, height=500,
            fit=ft.ImageFit.CONTAIN,
            error_content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=32, color=ft.Colors.GREY_600),
        )
        inner = ft.Container(
            padding=16,
            bgcolor=WHITE,
            content=ft.Column(
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("Vista previa", size=16, weight=ft.FontWeight.W_700),
                    big_img,
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[ft.OutlinedButton("Cerrar", on_click=lambda __: close_bs())]),
                ],
            ),
        )
        bs = ft.BottomSheet(content=inner, show_drag_handle=True, is_scroll_controlled=True)
        def close_bs():
            page.close(bs); page.update()
        page.open(bs)

    card = ft.Container(on_click=open_big_panel, content=_image_box(img_small), ink=True)

    root = ft.Container(
        bgcolor=ft.Colors.GREY_50,
        expand=True,
        padding=16,
        border_radius=12,
        content=ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Prueba: data-URL (click para ampliar)", size=16, weight=ft.FontWeight.W_600),
                card,
            ],
        ),
    )

    # auto-kickoff: carga A en background cuando el control está montado
    async def _defer_kickoff():
        # esperar a que img_small esté montada (máx ~3s)
        for _ in range(60):
            if getattr(img_small, "page", None):
                break
            await asyncio.sleep(0.05)
        page.run_task(load_data_url_async, DRIVE_URL_A)

    page.run_task(_defer_kickoff)

    return root
