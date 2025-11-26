# back/drive/permissions.py
from __future__ import annotations
from typing import Optional, Dict, List

from back.drive.drive_check import build_drive_service


# -- mapping de tu rango interno -> rol de Drive
def _role_from_rango(rango: str) -> str:
    r = (rango or "").strip().lower()
    if r in ("administrador", "admin"):
        return "writer"       # si querés "owner" deberías transferir propiedad (no recomendado)
    if r in ("editor",):
        return "writer"
    if r in ("visitante", "lector", "viewer", "lectura"):
        return "reader"
    # default seguro
    return "reader"


def list_permissions(page, file_id: str) -> List[Dict]:
    """Devuelve permisos actuales del archivo."""
    drive = build_drive_service(page)
    perms = drive.permissions().list(
        fileId=file_id,
        supportsAllDrives=True,
        fields="permissions(id,emailAddress,role,type,domain)",
    ).execute()
    return perms.get("permissions", []) or []


def _find_permission_by_email(perms: List[Dict], email: str) -> Optional[Dict]:
    email = (email or "").strip().lower()
    for p in perms:
        if (p.get("type") == "user") and (p.get("emailAddress", "").lower() == email):
            return p
    return None


def upsert_user_permission(
    page,
    file_id: str,
    email: str,
    rango: str,
    send_email: bool = False,
) -> Dict:
    """
    Crea o actualiza el permiso de Drive para 'email' según 'rango'.
    - Administrador/Editor -> writer
    - Visitante            -> reader
    """
    if not email:
        raise ValueError("Email requerido para otorgar permisos.")

    role = _role_from_rango(rango)
    drive = build_drive_service(page)

    perms = list_permissions(page, file_id)
    existing = _find_permission_by_email(perms, email)

    if existing:
        # si el rol cambió, actualizar
        if existing.get("role") != role:
            drive.permissions().update(
                fileId=file_id,
                permissionId=existing["id"],
                supportsAllDrives=True,
                body={"role": role},
                transferOwnership=False,
            ).execute()
            return {"status": "updated", "id": existing["id"], "role": role}
        else:
            return {"status": "unchanged", "id": existing["id"], "role": role}

    # crear nuevo
    created = drive.permissions().create(
        fileId=file_id,
        supportsAllDrives=True,
        sendNotificationEmail=send_email,
        body={
            "type": "user",
            "role": role,
            "emailAddress": email,
        },
        fields="id,role,emailAddress",
    ).execute()
    return {"status": "created", "id": created.get("id"), "role": created.get("role")}


def remove_permission_by_email(page, file_id: str, email: str) -> bool:
    """Elimina el permiso del email, si existe."""
    perms = list_permissions(page, file_id)
    p = _find_permission_by_email(perms, email)
    if not p:
        return False
    drive = build_drive_service(page)
    drive.permissions().delete(
        fileId=file_id,
        permissionId=p["id"],
        supportsAllDrives=True,
    ).execute()
    return True
