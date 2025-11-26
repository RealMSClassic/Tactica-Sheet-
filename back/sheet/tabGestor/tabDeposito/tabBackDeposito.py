# ./back/sheet/tabGestor/tabBackDeposito.py
from __future__ import annotations
from typing import List, Dict, Optional
from uuid import uuid4
import os
from back.integrations.drive_user_uploader import DriveUserUploader
try:
    from back.sheet.deposito_api import DepositoAPI
except Exception:
    DepositoAPI = None

try:
    from back.sheet.imagen_api import ImagenAPI
except Exception:
    ImagenAPI = None


class DepositoBackend:
    """
    Backend para Depósitos.
    - refresh_all / refresh_depositos / refresh_imagenes
    - filter(q)
    - add / update / delete
    - remove_image_for_deposito(recid)
    - upload_and_attach_image(...)
    Mapas:
    - depo_by_recid: RecID(deposito) -> dict
    - img_by_recid : RecID(imagen)   -> ID_nombre(link)
    """

    def __init__(self, page=None, bus: Optional[object] = None):
        self.page = page
        self.bus = bus

        # Si tu app guarda el Sheet ID en client_storage o contexto, podés leerlo aquí.
        self.sheet_id = None
        if page is not None:
            self.sheet_id = (
                page.client_storage.get("active_sheet_id")
                or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
            )

        self.api = DepositoAPI(page, self.sheet_id) if (DepositoAPI and page is not None) else None
        self.api_img = ImagenAPI(page, self.sheet_id) if (ImagenAPI and page is not None) else None

        self.depositos: List[Dict] = []
        self.depo_by_recid: Dict[str, Dict] = {}

        self.imagenes: List[Dict] = []
        # Mapa: RecID (imagen) -> ID_nombre (link)
        self.img_by_recid: Dict[str, str] = {}

    # -------- Opcional: poder inyectar page luego ----------
    def attach_page(self, page):
        self.page = page
        self.sheet_id = (
            page.client_storage.get("active_sheet_id")
            or getattr(getattr(page, "app_ctx", {}), "get", lambda *_: None)("sheet", {}).get("id", "")
        )
        self.api = DepositoAPI(page, self.sheet_id) if DepositoAPI else None
        self.api_img = ImagenAPI(page, self.sheet_id) if ImagenAPI else None

    # -------- Refresh ----------
    def refresh_imagenes(self):
        """Carga hoja 'imagen' y construye el mapa RecID -> link."""
        if not self.api_img:
            self.imagenes = []
            self.img_by_recid = {}
            return
        self.imagenes = self.api_img.list()
        self.img_by_recid = {(i.get("RecID") or ""): (i.get("ID_nombre") or "") for i in self.imagenes}

    def refresh_depositos(self):
        """Carga hoja 'deposito' y resuelve imagen_url desde img_by_recid."""
        self.refresh_imagenes()

        if not self.api:
            self.depositos = []
            self.depo_by_recid = {}
            return

        self.depositos = self.api.list()

        # Resolver RecID_imagen -> imagen_url (sin perder el RecID original)
        for d in self.depositos:
            rid = (d.get("RecID_imagen") or "").strip()
            link = self.img_by_recid.get(rid, "").strip()
            if link:
                d["imagen_url"] = link

        self.depo_by_recid = {d.get("RecID", ""): d for d in self.depositos}

    def refresh_all(self):
        self.refresh_depositos()  # ya refresca imágenes adentro

    # -------- Query helpers ----------
    def filter(self, q: str) -> List[Dict]:
        ql = (q or "").strip().lower()
        if not ql:
            return list(self.depositos)
        out = []
        for d in self.depositos:
            campos = [
                (d.get("nombre_deposito") or "").lower(),
                (d.get("id_deposito") or "").lower(),
                (d.get("direccion_deposito") or "").lower(),
                (d.get("descripcion_deposito") or "").lower(),
                (d.get("RecID_imagen") or "").lower(),
                (d.get("imagen_url") or "").lower(),
            ]
            if any(ql in c for c in campos):
                out.append(d)
        return out

    # -------- Bus ----------
    def _publish(self):
        if not self.bus:
            return
        try:
            self.bus.publish("depositos_changed", {})
        except Exception:
            pass

    # -------- CRUD ----------
    def add(self, *, id_deposito: str, nombre_deposito: str,
            direccion_deposito: str = "", descripcion_deposito: str = "",
            RecID_imagen: str = "") -> Optional[str]:
        if not self.api:
            return None
        recid = self.api.add(
            id_deposito=id_deposito,
            nombre_deposito=nombre_deposito,
            direccion_deposito=direccion_deposito,
            descripcion_deposito=descripcion_deposito,
            RecID_imagen=RecID_imagen,
        )
        self._publish()
        return recid

    def update(self, recid: str, *, id_deposito: Optional[str] = None,
               nombre_deposito: Optional[str] = None,
               direccion_deposito: Optional[str] = None,
               descripcion_deposito: Optional[str] = None,
               RecID_imagen: Optional[str] = None) -> bool:
        if not self.api:
            return False
        ok = self.api.update_by_recid(
            recid,
            id_deposito=id_deposito,
            nombre_deposito=nombre_deposito,
            direccion_deposito=direccion_deposito,
            descripcion_deposito=descripcion_deposito,
            RecID_imagen=RecID_imagen,
        )
        if ok:
            self._publish()
        return ok

    def _resolve_recid(self, recid_or_id: str) -> str:
        """Devuelve siempre el RecID real del depósito, aceptando RecID o id_deposito."""
        key = (recid_or_id or "").strip()
        if not key:
            return ""
        if key in self.depo_by_recid:
            return key
        for d in self.depositos or []:
            if d.get("RecID") == key or d.get("id_deposito") == key:
                return (d.get("RecID") or "").strip()
        return ""

    def delete(self, recid_or_id: str) -> bool:
        """
        Borra el depósito.
        - Resuelve el RecID real (acepta RecID o id_deposito)
        - Borra, si hay, la fila de 'imagen' asociada (RecID_imagen)
        - Llama a distintas variantes por compatibilidad con APIs
        """
        if not self.api:
            print("[DepositoBackend.delete] api no disponible", flush=True)
            return False

        recid = self._resolve_recid(recid_or_id)
        if not recid:
            print(f"[DepositoBackend.delete] recid inválido para key={recid_or_id!r}", flush=True)
            return False

        d = self.depo_by_recid.get(recid, {})
        rid_img = (d.get("RecID_imagen") or "").strip()

        # 1) Si hay imagen asociada, intentamos borrar la fila en 'imagen'
        if self.api_img and rid_img:
            try:
                ok_img = self.api_img.delete_by_recid(rid_img)
                print(f"[DepositoBackend.delete] delete imagen RecID={rid_img} -> {ok_img}", flush=True)
            except Exception as ex:
                print(f"[DepositoBackend.delete] delete imagen error: {ex}", flush=True)

        # 2) Intentar métodos de borrado compatibles
        ok = False
        tried = []

        def _try_call(name, *args, **kwargs):
            nonlocal ok, tried
            m = getattr(self.api, name, None)
            if callable(m):
                tried.append(name)
                try:
                    r = m(*args, **kwargs)
                    ok = bool(r)
                except Exception as ex:
                    print(f"[DepositoBackend.delete] {name} error: {ex}", flush=True)

        _try_call("delete_by_recid", recid)
        if not ok:
            _try_call("delete", recid)
        if not ok:
            _try_call("delete_row_by_recid", recid)
        if not ok:
            # fallback: borrar por condición (si la API lo soporta)
            _try_call("delete_where", {"RecID": recid})

        print(f"[DepositoBackend.delete] recid={recid} ok={ok} tried={tried}", flush=True)

        if ok:
            self.refresh_all()
            self._publish()
        return ok

    # -------- Imagen: remover vínculo en hojas (no borra archivo en Drive) ----------
    def remove_image_for_deposito(self, recid_deposito: str) -> bool:
        """
        1) Lee RecID_imagen del depósito (si existe).
        2) Vacía RecID_imagen en la hoja 'deposito'.
        3) Borra la fila correspondiente en la hoja 'imagen' por RecID.
        (No interactúa con Drive.)
        """
        if not self.api:
            return False
        recid_deposito = self._resolve_recid(recid_deposito)
        if not recid_deposito:
            return False

        d = self.depo_by_recid.get(recid_deposito, {})
        rid_img = (d.get("RecID_imagen") or "").strip()

        ok_upd = self.api.update_by_recid(recid_deposito, RecID_imagen="")

        ok_img = True
        if self.api_img and rid_img:
            try:
                ok_img = self.api_img.delete_by_recid(rid_img)
            except Exception:
                ok_img = False

        self.refresh_all()
        self._publish()
        return bool(ok_upd and ok_img)

    # -------- Subida + attach (EDIT) ----------
    def upload_and_attach_image(
        self,
        recid_deposito: str,
        local_path: str,
        folder_path: str = "TacticaGestorSheet/ImagenGestor",
    ) -> dict:
        """
        1) Sube `local_path` al Drive del USUARIO (usa page.auth.token).
        2) Inserta fila en hoja 'imagen': (RecID, ID_nombre=link de vista).
        3) Actualiza 'deposito.RecID_imagen' con ese RecID.
        4) Refresca caches / publica evento.
        5) Borra el archivo temporal local.

        Retorna: {'ok': bool, 'recid_imagen': str, 'imagen_url': str, 'error': str}
        """
        out = {"ok": False, "recid_imagen": "", "imagen_url": "", "error": ""}

        recid_deposito = self._resolve_recid(recid_deposito)
        local_path = (local_path or "").strip()

        # Validaciones
        if not self.api or not self.api_img:
            out["error"] = "APIs no disponibles"
            return out
        if not recid_deposito or not local_path:
            out["error"] = "Parámetros inválidos"
            return out
        if not os.path.isfile(local_path):
            out["error"] = f"Archivo local no encontrado: {local_path}"
            return out

        try:
            # 1) Uploader con la sesión OAuth actual (page.auth.token)
            uploader = DriveUserUploader.from_page(self.page)
            file_id, view_link = uploader.upload_to_path(local_path, folder_path, make_public=True)

            # 2) Fila en hoja 'imagen'
            recid_img = uuid4().hex[:10]
            ok_row = self.api_img.add(recid_img, view_link)  # add(RecID, ID_nombre)
            if not ok_row:
                out["error"] = "No se pudo insertar en hoja 'imagen'"
                try:
                    uploader.delete_file(file_id)
                except Exception:
                    pass
                return out

            # 3) Actualizar el depósito -> RecID_imagen
            ok_dep = self.api.update_by_recid(recid_deposito, RecID_imagen=recid_img)
            if not ok_dep:
                out["error"] = "No se pudo actualizar 'deposito.RecID_imagen'"
                try:
                    self.api_img.delete_by_recid(recid_img)
                except Exception:
                    pass
                try:
                    uploader.delete_file(file_id)
                except Exception:
                    pass
                return out

            # 4) Refrescar memoria y notificar
            self.refresh_all()
            self._publish()

            # 5) Borrar el archivo temporal local
            try:
                os.remove(local_path)
            except Exception:
                pass

            out.update({"ok": True, "recid_imagen": recid_img, "imagen_url": view_link})
            return out

        except Exception as ex:
            out["error"] = f"{ex}"
            return out
