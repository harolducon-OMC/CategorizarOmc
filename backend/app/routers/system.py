"""Estado del servicio, proveedores de IA y asistente de ayuda.

Movido desde main.py sin cambios de comportamiento.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import help_assistant
from core.llm import PROVIDER_CONFIG
from ..common import _api_key_for_user
from ..db import get_db
from ..ratelimit import limit_by_user
from ..schemas import HelpChatRequest
from ..services import create_llm

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "connected"}


@router.get("/api/config/providers")
def providers():
    return [{"id": key, "name": item["name"], "default_model": item["default_model"], "models": item["models"]}
            for key, item in PROVIDER_CONFIG.items()]


@router.post("/api/help/chat", dependencies=[Depends(limit_by_user("help-chat", 20, 60))])
def platform_help_chat(
    payload: HelpChatRequest, http_request: Request, db: Session = Depends(get_db),
    api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
):
    if payload.messages[-1].role != "user":
        raise HTTPException(422, "El último mensaje debe ser una pregunta del usuario.")
    api_key = _api_key_for_user(db, http_request.state.user_email, payload.provider, api_key)
    if not api_key:
        offline_answer = help_assistant.answer_without_model(
            [message.model_dump() for message in payload.messages]
        )
        if offline_answer:
            return {"answer": offline_answer}
    llm = create_llm(payload.provider, payload.model, api_key)
    try:
        response = help_assistant.answer_question(
            llm, [message.model_dump() for message in payload.messages]
        )
    except Exception as exc:
        logger.exception("Fallo en platform_help_chat")
        raise HTTPException(502, f"No se pudo responder la pregunta: {exc}") from exc
    return {"answer": response}
