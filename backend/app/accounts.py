"""Cuentas: roles, estado (activa, inactiva, baneada), permisos del panel de administración y arranque seguro.

Roles
- user: usuario normal (todo registro nuevo empieza aquí).
- admin: administra cuentas y políticas, pero no asigna el rol de administrador.
- super_admin: único en la plataforma (la base de datos lo garantiza). Es el único que asigna o quita el
  rol de administrador. Se identifica con la variable de entorno SUPERADMIN_EMAIL.
"""
import logging
import os
import threading
import time
import uuid
from typing import Dict, Optional

logger = logging.getLogger(__name__)

ROLE_USER, ROLE_ADMIN, ROLE_SUPER = "user", "admin", "super_admin"
ADMIN_ROLES = {ROLE_ADMIN, ROLE_SUPER}

# ---------------------------------------------------------------- permisos (lógica pura, probada en tests)
ACTIONS_NEED_OTHER_ACCOUNT = {"deactivate", "ban", "delete", "role", "reset_password"}


def permission_error(actor_role: str, target_role: str, action: str, is_self: bool) -> Optional[str]:
    """Devuelve el motivo por el que NO se permite la acción, o None si se permite."""
    if actor_role not in ADMIN_ROLES:
        return "Esta acción requiere permisos de administrador."
    if is_self and action in ACTIONS_NEED_OTHER_ACCOUNT:
        if action == "reset_password":
            return "Para cambiar tu propia contraseña usa «Cambiar mi contraseña»."
        return "No puedes hacer esto sobre tu propia cuenta."
    if target_role == ROLE_SUPER:
        return "La cuenta de super administrador no se puede modificar desde el panel."
    if action == "role" and actor_role != ROLE_SUPER:
        return "Solo el super administrador puede asignar o quitar el rol de administrador."
    if actor_role == ROLE_ADMIN and target_role == ROLE_ADMIN:
        return "Un administrador no puede actuar sobre otro administrador. Pídelo al super administrador."
    return None


def account_state(user) -> str:
    if user.banned_at is not None:
        return "banned"
    if not user.is_active:
        return "inactive"
    return "active"


# ---------------------------------------------------------------- estado en caché para el middleware
_STATUS_TTL = 10.0
_status_cache: Dict[str, tuple] = {}
_status_lock = threading.Lock()


def account_status(email: str) -> Optional[dict]:
    """Datos mínimos de la cuenta para validar cada petición (caché de 10 s; los cambios de admin la invalidan)."""
    from sqlalchemy import func, select
    email = email.strip().lower()
    now = time.monotonic()
    with _status_lock:
        cached = _status_cache.get(email)
        if cached and cached[0] > now:
            return cached[1]
    from .auth_models import User
    from .db import SessionLocal
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        status = None if user is None else {
            "id": user.id, "email": user.email, "role": user.role, "active": bool(user.is_active),
            "banned": user.banned_at is not None, "must_change_password": bool(user.must_change_password),
            "token_version": int(user.token_version or 0),
        }
    with _status_lock:
        _status_cache[email] = (now + _STATUS_TTL, status)
        if len(_status_cache) > 5000:
            _status_cache.clear()
    return status


def invalidate(email: str) -> None:
    with _status_lock:
        _status_cache.pop(email.strip().lower(), None)


# ---------------------------------------------------------------- arranque
USER_COLUMN_DDL = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_by VARCHAR(320)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_single_super_admin ON users (role) WHERE role = 'super_admin'",
]


def ensure_schema(connection) -> None:
    """Agrega las columnas nuevas de `users` si faltan (create_all no modifica tablas existentes). Idempotente."""
    from sqlalchemy import text
    if connection.dialect.name != "postgresql":
        return
    for statement in USER_COLUMN_DDL:
        connection.execute(text(statement))


def superadmin_email() -> str:
    return os.getenv("SUPERADMIN_EMAIL", "").strip().lower()


def super_admin_exists(db) -> bool:
    from sqlalchemy import func, select
    from .auth_models import User
    return db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_SUPER)) > 0


def ensure_super_admin(db) -> Optional[str]:
    """Si no hay super administrador y SUPERADMIN_EMAIL corresponde a un usuario existente, lo promueve."""
    from sqlalchemy import func, select
    from .auth_models import User
    email = superadmin_email()
    if not email or super_admin_exists(db):
        return None
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        return None
    user.role = ROLE_SUPER
    db.commit()
    invalidate(email)
    logger.warning("Super administrador asignado a %s", email)
    return email


def new_user_role(db, email: str) -> str:
    """Todo registro nuevo es «user»; solo SUPERADMIN_EMAIL puede ser super administrador (y solo si aún no hay uno)."""
    if email.strip().lower() == superadmin_email() and not super_admin_exists(db):
        return ROLE_SUPER
    return ROLE_USER


def audit(db, actor_email: str, action: str, target_email: Optional[str] = None, details: Optional[dict] = None) -> None:
    from .auth_models import AdminAuditLog
    db.add(AdminAuditLog(id=uuid.uuid4().hex, actor_email=actor_email, action=action,
                         target_email=target_email, details=details or {}))
