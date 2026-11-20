"""Panel de administración: cuentas, políticas de seguridad y auditoría.

Reglas (ver app/accounts.py::permission_error):
- admin: puede inactivar, banear, restablecer contraseñas, eliminar cuentas de usuarios y editar políticas.
- super_admin (único): además es el único que asigna o quita el rol de administrador.
- Nadie puede actuar sobre su propia cuenta ni sobre el super administrador desde el panel.
- El panel muestra cuentas y conteos; nunca el contenido de los estudios de las personas.
"""
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from core.llm import PROVIDER_CONFIG
from .. import accounts, policies
from ..auth_models import AdminAuditLog, User
from ..db import get_db
from ..models import Study
from ..ratelimit import limit_by_user
from ..security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(limit_by_user("admin", 120, 60))])


def current_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Quien hace la petición, verificado contra la base de datos (no solo contra la caché del middleware)."""
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None or user.role not in accounts.ADMIN_ROLES or user.banned_at is not None or not user.is_active:
        raise HTTPException(403, "Esta acción requiere permisos de administrador.")
    return user


def _target(db: Session, user_id: str) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    return target


def _authorize(actor: User, target: User, action: str) -> None:
    reason = accounts.permission_error(actor.role, target.role, action, actor.id == target.id)
    if reason:
        raise HTTPException(403, reason)


def _user_json(user: User, study_count: int = 0) -> dict:
    return {
        "id": user.id, "email": user.email, "role": user.role, "status": accounts.account_state(user),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "banned_at": user.banned_at.isoformat() if user.banned_at else None,
        "ban_reason": user.ban_reason, "banned_by": user.banned_by,
        "must_change_password": bool(user.must_change_password), "study_count": study_count,
        "locked": bool(user.locked_until and user.locked_until > datetime.now(timezone.utc)),
    }


def _close_sessions(user: User) -> None:
    """Invalida los tokens ya emitidos: la persona tendrá que iniciar sesión de nuevo."""
    user.token_version = (user.token_version or 0) + 1
    accounts.invalidate(user.email)


# ------------------------------------------------------------------ cuentas
@router.get("/api/admin/users")
def list_users(
    q: str = "", status: Literal["all", "active", "inactive", "banned"] = "all", limit: int = 50, offset: int = 0,
    actor: User = Depends(current_admin), db: Session = Depends(get_db),
):
    query = select(User)
    if q.strip():
        query = query.where(func.lower(User.email).contains(q.strip().lower(), autoescape=True))
    if status == "banned":
        query = query.where(User.banned_at.is_not(None))
    elif status == "inactive":
        query = query.where(and_(User.banned_at.is_(None), User.is_active.is_(False)))
    elif status == "active":
        query = query.where(and_(User.banned_at.is_(None), User.is_active.is_(True)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    users = db.scalars(query.order_by(User.created_at.desc()).limit(max(1, min(limit, 200))).offset(max(offset, 0))).all()
    counts = {}
    if users:
        counts = dict(db.execute(
            select(Study.owner_id, func.count(Study.id)).where(Study.owner_id.in_([u.id for u in users])).group_by(Study.owner_id)
        ).all())
    return {"total": total, "users": [_user_json(user, counts.get(user.id, 0)) for user in users], "viewer_role": actor.role}


@router.post("/api/admin/users/{user_id}/deactivate")
def deactivate_user(user_id: str, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    """Inactiva la cuenta de alguien que ya no hace parte de la organización (reversible)."""
    target = _target(db, user_id)
    _authorize(actor, target, "deactivate")
    target.is_active = False
    target.deactivated_at = datetime.now(timezone.utc)
    _close_sessions(target)
    accounts.audit(db, actor.email, "deactivate", target.email)
    db.commit()
    return _user_json(target)


@router.post("/api/admin/users/{user_id}/reactivate")
def reactivate_user(user_id: str, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    target = _target(db, user_id)
    _authorize(actor, target, "deactivate")
    target.is_active = True
    target.deactivated_at = None
    accounts.invalidate(target.email)
    accounts.audit(db, actor.email, "reactivate", target.email)
    db.commit()
    return _user_json(target)


class BanPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@router.post("/api/admin/users/{user_id}/ban")
def ban_user(user_id: str, payload: BanPayload, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    """Suspende la cuenta por incumplir las políticas. Queda el motivo y se cierran sus sesiones."""
    target = _target(db, user_id)
    _authorize(actor, target, "ban")
    target.banned_at = datetime.now(timezone.utc)
    target.ban_reason = payload.reason.strip()
    target.banned_by = actor.email
    _close_sessions(target)
    accounts.audit(db, actor.email, "ban", target.email, {"reason": target.ban_reason})
    db.commit()
    return _user_json(target)


@router.post("/api/admin/users/{user_id}/unban")
def unban_user(user_id: str, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    target = _target(db, user_id)
    _authorize(actor, target, "ban")
    target.banned_at, target.ban_reason, target.banned_by = None, None, None
    accounts.invalidate(target.email)
    accounts.audit(db, actor.email, "unban", target.email)
    db.commit()
    return _user_json(target)


@router.post("/api/admin/users/{user_id}/reset-password")
def reset_password(user_id: str, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    """Genera una contraseña temporal (se muestra UNA vez). La persona debe cambiarla al iniciar sesión."""
    target = _target(db, user_id)
    _authorize(actor, target, "reset_password")
    policy = policies.get_policy()
    temporary = policies.generate_temporary_password(max(16, policy["min_password_length"]))
    target.password_hash = hash_password(temporary)
    target.must_change_password = True
    target.password_changed_at = datetime.now(timezone.utc)
    target.failed_attempts, target.locked_until = 0, None
    _close_sessions(target)
    accounts.audit(db, actor.email, "reset_password", target.email)  # nunca se registra la contraseña
    db.commit()
    return {
        "email": target.email, "temporary_password": temporary,
        "note": "Entrégala por un canal seguro. No se volverá a mostrar y la persona deberá cambiarla al entrar.",
    }


@router.delete("/api/admin/users/{user_id}")
def delete_user(user_id: str, confirm_email: str, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    """Elimina la cuenta y TODOS sus estudios y clasificaciones. Irreversible: exige escribir el correo."""
    target = _target(db, user_id)
    _authorize(actor, target, "delete")
    if confirm_email.strip().lower() != target.email.lower():
        raise HTTPException(400, "El correo de confirmación no coincide con la cuenta.")
    email, studies = target.email, db.scalar(select(func.count(Study.id)).where(Study.owner_id == target.id))
    accounts.audit(db, actor.email, "delete", email, {"studies_deleted": studies})
    db.delete(target)
    db.commit()
    accounts.invalidate(email)
    return {"deleted": email, "studies_deleted": studies}


class RolePayload(BaseModel):
    role: Literal["admin", "user"]


@router.put("/api/admin/users/{user_id}/role")
def set_role(user_id: str, payload: RolePayload, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    """Solo el super administrador asigna o quita el rol de administrador."""
    target = _target(db, user_id)
    _authorize(actor, target, "role")
    if payload.role == "admin" and (target.banned_at is not None or not target.is_active):
        raise HTTPException(409, "Solo se puede nombrar administrador a una cuenta activa.")
    previous = target.role
    target.role = payload.role
    accounts.invalidate(target.email)
    accounts.audit(db, actor.email, "set_role", target.email, {"from": previous, "to": payload.role})
    db.commit()
    return _user_json(target)


# ------------------------------------------------------------------ políticas de seguridad
@router.get("/api/admin/policies")
def get_policies(actor: User = Depends(current_admin)):
    return {
        "policy": policies.get_policy(), "defaults": policies.default_policy(),
        "fields": {key: {"type": kind, "min": low, "max": high, "label": label} for key, (kind, low, high, label) in policies.POLICY_FIELDS.items()},
        "providers": [{"id": key, "name": value.get("name", key)} for key, value in PROVIDER_CONFIG.items()],
    }


class PolicyPayload(BaseModel):
    changes: dict


@router.put("/api/admin/policies")
def update_policies(payload: PolicyPayload, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    try:
        cleaned = policies.clean_policy(payload.changes)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not cleaned:
        raise HTTPException(422, "No hay cambios para guardar.")
    before = policies.get_policy()
    changed = {key: {"from": before.get(key), "to": value} for key, value in cleaned.items() if before.get(key) != value}
    policies.save_policy(db, cleaned, actor.email)
    accounts.audit(db, actor.email, "update_policy", None, changed)
    db.commit()
    return {"policy": policies.get_policy(), "changed": list(changed)}


# ------------------------------------------------------------------ auditoría
@router.get("/api/admin/audit")
def audit_log(limit: int = 100, actor: User = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(max(1, min(limit, 300)))).all()
    return {"events": [
        {"id": row.id, "actor": row.actor_email, "action": row.action, "target": row.target_email,
         "details": row.details or {}, "created_at": row.created_at.isoformat()}
        for row in rows
    ]}
