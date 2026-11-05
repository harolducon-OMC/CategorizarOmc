"""Registro, inicio de sesión y claves de IA del usuario.

Movido desde main.py sin cambios de comportamiento.
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.llm import PROVIDER_CONFIG
from ..auth_models import User, UserApiKey
from ..db import get_db
from ..ratelimit import enforce, limit_by_ip
from ..security import create_access_token, decrypt_api_key, email_is_allowed, encrypt_api_key, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter()


class AuthPayload(BaseModel):
    email: str = Field(min_length=6, max_length=320)
    password: str = Field(min_length=12, max_length=256)


class ApiKeyPayload(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)


@router.post("/api/auth/register", dependencies=[Depends(limit_by_ip("register", 10, 3600))])
def register(payload: AuthPayload, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+", email):
        raise HTTPException(422, "Ingresa un correo electrónico válido.")
    if not email_is_allowed(email):
        raise HTTPException(403, "El registro solo permite correos del dominio corporativo configurado.")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo.")
    user = User(id=uuid.uuid4().hex, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    return {"access_token": create_access_token(email), "token_type": "bearer", "email": email}


@router.post("/api/auth/login", dependencies=[Depends(limit_by_ip("login", 60, 300))])
def login(payload: AuthPayload, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    enforce("login-email", email, 8, 300)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    return {"access_token": create_access_token(user.email), "token_type": "bearer", "email": user.email}


@router.get("/api/auth/me")
def current_user(request: Request):
    return {"email": request.state.user_email}


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
