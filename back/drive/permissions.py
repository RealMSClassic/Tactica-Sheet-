# back/drive/permissions.py
from __future__ import annotations
from typing import Optional, List, Dict

from googleapiclient.errors import HttpError

from back.drive.drive_check import build_drive_service

# Mapeo de tus rangos -> roles de Drive
ROLE_MAP = {
    "Administrador": "writer",   # no intentamos transferir ownership
    "Editor":        "writer",
    "Visitante":     "reader",
}
DEFAULT_ROLE = "reader"


def role_to_drive(rango: str) -> str:
    return ROLE_MAP.get((rango or "").strip().capitalize(), DEFAULT_ROLE)


def sheet_web_link(file_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"


def list_permissions(page, file_id: str) -> List[Dict]:
    """Devuelve la lista de permisos actuales (id, type, role, emailAddress si está disponible)."""
    drive = build_drive_service(page)
    res = drive.permissions().list(
        fileId=file_id,
        fields="permissions(id,type,role,emailAddress,domain,allowFileDiscovery)",
        supportsAllDrives=True,
    ).execute()
    perms = res.get("permissions", []) or []
    print("[PERMS] actuales:", perms)
    return perms


def upsert_user_permission(
    page,
    file_id: str,
    email: str,
    rango: str,
    send_email: bool = True,
) -> str:
    """
    Crea o actualiza el permiso para 'email' en 'file_id'.
    Devuelve el permissionId creado/actualizado.
    """
    drive = build_drive_service(page)
    target_role = role_to_drive(rango)
    email_l = (email or "").strip().lower()
    if not email_l:
        raise ValueError("Email vacío.")

    # 1) Buscar si ya existe permiso para ese email
    perms = list_permissions(page, file_id)
    found = next(
        (p for p in perms
         if p.get("type") == "user"
         and (p.get("emailAddress", "") or "").lower() == email_l),
        None
    )

    if found:
        # 2) Si existe y el rol es distinto, actualizarlo
        if found.get("role") != target_role:
            print(f"[PERMS] update -> {email_l} : {found.get('role')} -> {target_role}")
            drive.permissions().update(
                fileId=file_id,
                permissionId=found["id"],
                body={"role": target_role},
                supportsAllDrives=True,
            ).execute()
        else:
            print(f"[PERMS] sin cambios (ya {target_role}) para {email_l}")
        return found["id"]

    # 3) No existe -> crearlo
    print(f"[PERMS] create -> {email_l} as {target_role}")
    created = drive.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": target_role, "emailAddress": email_l},
        sendNotificationEmail=send_email,
        supportsAllDrives=True,
        fields="id",
    ).execute()
    return created.get("id", "")
