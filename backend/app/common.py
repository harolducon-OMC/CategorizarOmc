"""Utilidades compartidas por los routers (serializadores y dependencias)."""
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import coding
from .auth_models import User, UserApiKey
from .db import get_db
from .models import Classification, ClassificationDraft, Study
from .security import decrypt_api_key
from .services import get_user_id


def _study_json(study: Study) -> dict:
    return {
        "id": study.id, "name": study.name, "source_filename": study.source_filename,
        "columns": study.columns, "row_count": study.row_count,
        "created_at": study.created_at.isoformat() if study.created_at else None,
    }


def _classification_json(item: Classification) -> dict:
    return {
        "id": item.id, "study_id": item.study_id, "question": item.question,
        "kind": item.kind, "categories": item.categories, "codeframe": item.codeframe,
        "entities": item.entities, "aliases": item.aliases,
        "config": item.config, "has_insights": bool(item.insights),
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _draft_json(item: ClassificationDraft) -> dict:
    return {
        "id": item.id, "study_id": item.study_id, "question": item.question,
        "kind": item.kind, "codeframe": item.codeframe, "known_brands": item.known_brands,
        "context": item.context, "multi": item.multi, "provider": item.provider,
        "model": item.model, "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def get_current_user_id(request: Request, db: Session = Depends(get_db)) -> str:
    return get_user_id(db, request.state.user_email)


def _class_or_404(db: Session, classification_id: str, owner_id: str) -> Classification:
    item = db.scalar(
        select(Classification)
        .join(Study, Classification.study_id == Study.id)
        .where(Classification.id == classification_id, Study.owner_id == owner_id)
    )
    if item is None:
        raise HTTPException(404, "No se encontró la clasificación.")
    return item


def _labels_without_blank_responses(labels, responses):
    """Limpia resultados antiguos: si la respuesta fuente está vacía, la etiqueta también."""
    stored = labels or []
    return [
        [] if coding.is_blank_response(response)
        else list(stored[index] or []) if index < len(stored)
        else []
        for index, response in enumerate(responses)
    ]


def _api_key_for_user(db: Session, email: str, provider: str, supplied: Optional[str]) -> Optional[str]:
    """La clave temporal del header prevalece; si falta, carga la clave cifrada del usuario."""
    if supplied and supplied.strip():
        return supplied.strip()
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    saved = db.get(UserApiKey, {"user_id": user.id, "provider": provider})
    if not saved:
        return None
    try:
        return decrypt_api_key(saved.encrypted_key)
    except RuntimeError as exc:
        raise HTTPException(400, "La clave guardada ya no se puede leer (cambió JWT_SECRET en el servidor). Vuelve a guardarla en Ajustes.") from exc
