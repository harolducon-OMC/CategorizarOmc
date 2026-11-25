"""Escucha social: credenciales independientes y análisis efímero de menciones."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import social_listening as social_core
from ..auth_models import UserApiKey
from ..db import get_db
from ..ratelimit import limit_by_user
from ..security import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

SOCIAL_KEY_IDS = {
    "xpoz": "social_xpoz",
    "gemini": "social_gemini",
    "groq": "social_groq",
}
ALLOWED_PLATFORMS = {"Twitter", "Instagram", "Tiktok", "Reddit"}
ALLOWED_LANGUAGES = {"es", "en", "pt", "fr"}


class SocialKeyPayload(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)


class SocialAnalysisPayload(BaseModel):
    brand: str = Field(min_length=1, max_length=120)
    max_mentions: int = Field(default=60, ge=10, le=200)
    platforms: list[str] = Field(default_factory=lambda: ["Twitter", "Reddit"], max_length=4)
    languages: list[str] = Field(default_factory=lambda: ["es"], max_length=4)
    with_comments: bool = False
    provider: Literal["gemini", "groq"] = "gemini"
    model: str = Field(min_length=1, max_length=160)


def _record(db: Session, user_id: str, key_id: str) -> UserApiKey | None:
    return db.get(UserApiKey, {"user_id": user_id, "provider": key_id})


def _load_key(db: Session, user_id: str, name: str) -> str:
    key_id = SOCIAL_KEY_IDS[name]
    row = _record(db, user_id, key_id)
    if row is None:
        raise HTTPException(400, f"Falta configurar la clave de {name.upper()} en Ajustes → Escucha social.")
    try:
        return decrypt_api_key(row.encrypted_key)
    except RuntimeError as exc:
        raise HTTPException(400, f"La clave guardada de {name.upper()} no se puede descifrar. Vuelve a guardarla en Ajustes → Escucha social.") from exc


@router.get("/api/me/social-listening/keys")
def list_social_keys(request: Request, db: Session = Depends(get_db)):
    user_id = request.state.user_id
    configured, unreadable = [], []
    for name, key_id in SOCIAL_KEY_IDS.items():
        row = _record(db, user_id, key_id)
        if row is None:
            continue
        try:
            decrypt_api_key(row.encrypted_key)
            configured.append(name)
        except RuntimeError:
            unreadable.append(name)
    return {"configured": configured, "unreadable": unreadable}


@router.put("/api/me/social-listening/keys/{name}")
def save_social_key(name: str, payload: SocialKeyPayload, request: Request, db: Session = Depends(get_db)):
    if name not in SOCIAL_KEY_IDS:
        raise HTTPException(404, "Tipo de clave de escucha social no reconocido.")
    value = payload.api_key.strip()
    if not value:
        raise HTTPException(422, "La clave no puede estar vacía.")
    user_id = request.state.user_id
    key_id = SOCIAL_KEY_IDS[name]
    row = _record(db, user_id, key_id)
    if row is None:
        row = UserApiKey(user_id=user_id, provider=key_id, encrypted_key=encrypt_api_key(value))
        db.add(row)
    else:
        row.encrypted_key = encrypt_api_key(value)
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"name": name, "configured": True}


@router.delete("/api/me/social-listening/keys/{name}")
def delete_social_key(name: str, request: Request, db: Session = Depends(get_db)):
    if name not in SOCIAL_KEY_IDS:
        raise HTTPException(404, "Tipo de clave de escucha social no reconocido.")
    row = _record(db, request.state.user_id, SOCIAL_KEY_IDS[name])
    if row is not None:
        db.delete(row)
        db.commit()
    return {"name": name, "configured": False}


@router.post("/api/social-listening/analyze", dependencies=[Depends(limit_by_user("social-listening", 5, 600))])
def analyze_social(request_payload: SocialAnalysisPayload, request: Request, db: Session = Depends(get_db)):
    """Consulta Xpoz y clasifica en el proveedor social elegido; no guarda las menciones."""
    brand = request_payload.brand.strip()
    if not brand:
        raise HTTPException(422, "Escribe una marca o palabra clave.")
    model = request_payload.model.strip()
    if not model:
        raise HTTPException(422, "Indica el ID del modelo de Gemini o Groq.")
    if any(item not in ALLOWED_PLATFORMS for item in request_payload.platforms):
        raise HTTPException(422, "Una o más redes sociales no son válidas.")
    if any(item not in ALLOWED_LANGUAGES for item in request_payload.languages):
        raise HTTPException(422, "Uno o más idiomas no son válidos.")

    user_id = request.state.user_id
    xpoz_key = _load_key(db, user_id, "xpoz")
    llm_key = _load_key(db, user_id, request_payload.provider)
    db.close()  # No retener conexión de PostgreSQL durante las llamadas externas.

    try:
        mentions = asyncio.run(social_core.collect(
            brand=brand,
            limit=request_payload.max_mentions,
            platforms=request_payload.platforms or None,
            xpoz_key=xpoz_key,
            langs=request_payload.languages or None,
            with_comments=request_payload.with_comments,
        ))
        if mentions:
            mentions = social_core.classify(
                brand=brand,
                mentions=mentions,
                provider=request_payload.provider,
                model=model,
                api_key=llm_key,
            )
        summary = social_core.report(brand, mentions)
        safe_mentions = [
            {
                "platform": str(item.get("platform", ""))[:40],
                "kind": str(item.get("kind", "post"))[:24],
                "text": str(item.get("text", ""))[:1000],
                "url": str(item.get("url", ""))[:1000],
                "language": str(item.get("lang", ""))[:12],
                "location": str(item.get("location", ""))[:120],
                "analysis": item.get("analysis", {}),
            }
            for item in mentions
            if isinstance(item.get("analysis"), dict)
        ]
        return {"summary": summary, "mentions": safe_mentions}
    except HTTPException:
        raise
    except Exception as exc:
        # No incluir textos, cuerpos del proveedor ni credenciales en logs o respuestas.
        logger.warning("Escucha social fallida (%s)", type(exc).__name__)
        raise HTTPException(502, "No se pudo completar el análisis social. Verifica las claves y el proveedor, y vuelve a intentarlo.") from exc
