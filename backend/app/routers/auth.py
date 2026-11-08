"""Registro, inicio de sesión y claves de IA del usuario.

Movido desde main.py sin cambios de comportamiento.
"""
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.llm import PROVIDER_CONFIG
from .. import accounts, policies
from ..auth_models import User, UserApiKey
from ..db import get_db
from ..ratelimit import enforce, limit_by_ip, limit_by_user
from ..security import create_access_token, decrypt_api_key, email_is_allowed, encrypt_api_key, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter()


class AuthPayload(BaseModel):
    email: str = Field(min_length=6, max_length=320)
    password: str = Field(min_length=12, max_length=256)


class ApiKeyPayload(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)


class ChangePasswordPayload(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


def _session(user: User, policy: dict) -> dict:
    return {
        "access_token": create_access_token(user.email, user.token_version, policy["session_minutes"]),
        "token_type": "bearer", "email": user.email, "role": user.role,
        "must_change_password": bool(user.must_change_password),
    }


@router.post("/api/auth/register", dependencies=[Depends(limit_by_ip("register", 10, 3600))])
def register(payload: AuthPayload, db: Session = Depends(get_db)):
    policy = policies.get_policy()
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+", email):
        raise HTTPException(422, "Ingresa un correo electrónico válido.")
    if not policy["registration_enabled"]:
        raise HTTPException(403, "El registro de cuentas nuevas está cerrado por la política de la organización.")
    if not policies.email_domain_ok(email, policy):
        raise HTTPException(403, "El registro solo permite correos del dominio corporativo configurado.")
    problems = policies.password_problems(payload.password, policy)
    if problems:
        raise HTTPException(422, " ".join(problems))
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo.")
    # Todo registro nuevo es «user»; solo SUPERADMIN_EMAIL puede ser super administrador (y solo si aún no hay uno)
    user = User(
        id=uuid.uuid4().hex, email=email, password_hash=hash_password(payload.password),
        role=accounts.new_user_role(db, email), password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    return _session(user, policy)


@router.post("/api/auth/login", dependencies=[Depends(limit_by_ip("login", 60, 300))])
def login(payload: AuthPayload, db: Session = Depends(get_db)):
    policy = policies.get_policy()
    email = payload.email.strip().lower()
    enforce("login-email", email, 8, 300)
    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None and user.locked_until is not None and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise HTTPException(423, f"Cuenta bloqueada temporalmente por intentos fallidos. Intenta de nuevo en {minutes} min.")
    if not user or not verify_password(payload.password, user.password_hash):
        if user is not None:
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= policy["max_failed_logins"]:
                user.locked_until = now + timedelta(minutes=policy["lockout_minutes"])
                user.failed_attempts = 0
                logger.warning("Cuenta bloqueada por intentos fallidos: %s", user.email)
            db.commit()
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    # El estado de la cuenta solo se revela después de acertar la contraseña
    if user.banned_at is not None:
        raise HTTPException(403, "Tu cuenta está suspendida por incumplir las políticas de la plataforma. Contacta al administrador.")
    if not user.is_active:
        raise HTTPException(403, "Tu cuenta está inactiva. Contacta al administrador si crees que es un error.")
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    return _session(user, policy)


@router.get("/api/auth/me")
def current_user(request: Request):
    return {
        "email": request.state.user_email,
        "role": getattr(request.state, "user_role", accounts.ROLE_USER),
        "must_change_password": getattr(request.state, "must_change_password", False),
    }


@router.post("/api/auth/change-password", dependencies=[Depends(limit_by_user("change-password", 10, 600))])
def change_password(payload: ChangePasswordPayload, request: Request, db: Session = Depends(get_db)):
    """Cambio de contraseña propio (también es el paso obligatorio tras un restablecimiento del administrador)."""
    policy = policies.get_policy()
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta.")
    if payload.new_password == payload.current_password:
        raise HTTPException(422, "La nueva contraseña debe ser distinta de la actual.")
    problems = policies.password_problems(payload.new_password, policy)
    if problems:
        raise HTTPException(422, " ".join(problems))
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.now(timezone.utc)
    user.token_version = (user.token_version or 0) + 1  # cierra las demás sesiones abiertas
    user.failed_attempts, user.locked_until = 0, None
    db.commit()
    accounts.invalidate(user.email)
    return _session(user, policy)


@router.get("/api/me/api-keys")
def list_my_api_keys(request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    records = db.scalars(select(UserApiKey).where(UserApiKey.user_id == user.id)).all()
    unreadable = []
    for record in records:
        try:
            decrypt_api_key(record.encrypted_key)
        except RuntimeError:
            unreadable.append(record.provider)
    return {"providers": [record.provider for record in records], "unreadable": unreadable}


@router.put("/api/me/api-keys/{provider}")
def save_my_api_key(provider: str, payload: ApiKeyPayload, request: Request, db: Session = Depends(get_db)):
    if provider not in PROVIDER_CONFIG:
        raise HTTPException(400, "Proveedor de IA no reconocido.")
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(422, "La API key es obligatoria y no puede superar 4096 caracteres.")
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    record = db.get(UserApiKey, {"user_id": user.id, "provider": provider})
    if record is None:
        record = UserApiKey(user_id=user.id, provider=provider, encrypted_key=encrypt_api_key(api_key))
        db.add(record)
    else:
        record.encrypted_key = encrypt_api_key(api_key)
        record.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"provider": provider, "configured": True, "updated_at": record.updated_at.isoformat()}


@router.delete("/api/me/api-keys/{provider}")
def delete_my_api_key(provider: str, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    record = db.get(UserApiKey, {"user_id": user.id, "provider": provider})
    if record is not None:
        db.delete(record)
        db.commit()
    return {"provider": provider, "configured": False}
