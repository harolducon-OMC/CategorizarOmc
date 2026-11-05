"""Estado del servicio, proveedores de IA y asistente de ayuda.

Movido desde main.py sin cambios de comportamiento.
"""
import json
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import help_assistant
from core.llm import PROVIDER_CONFIG
from ..common import _api_key_for_user
from ..db import get_db
from ..ratelimit import limit_by_ip, limit_by_user
from ..schemas import HelpChatRequest
from ..services import create_llm

logger = logging.getLogger(__name__)
vitals_logger = logging.getLogger("insights.vitals")
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


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/api/help/chat/stream", dependencies=[Depends(limit_by_user("help-chat", 20, 60))])
def platform_help_chat_stream(
    payload: HelpChatRequest, http_request: Request, db: Session = Depends(get_db),
    api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
):
    """Respuesta del asistente por Server-Sent Events: cada evento trae un fragmento («delta»)."""
    if payload.messages[-1].role != "user":
        raise HTTPException(422, "El último mensaje debe ser una pregunta del usuario.")
    api_key = _api_key_for_user(db, http_request.state.user_email, payload.provider, api_key)
    messages = [message.model_dump() for message in payload.messages]

    def events():
        try:
            if not api_key:
                offline_answer = help_assistant.answer_without_model(messages)
                if offline_answer:
                    yield _sse({"delta": offline_answer})
                    yield _sse({"done": True})
                    return
            llm = create_llm(payload.provider, payload.model, api_key)
            for piece in help_assistant.stream_answer(llm, messages):
                yield _sse({"delta": piece})
            yield _sse({"done": True})
        except HTTPException as exc:
            yield _sse({"error": str(exc.detail)})
        except Exception as exc:
            logger.exception("Fallo en platform_help_chat_stream")
            yield _sse({"error": f"No se pudo responder la pregunta: {exc}"})

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Content-Encoding": "identity",
    })


class VitalPayload(BaseModel):
    name: Literal["LCP", "CLS", "INP", "FCP", "TTFB"]
    value: float = Field(ge=0, le=600000)
    rating: Optional[Literal["good", "needs-improvement", "poor"]] = None
    page: str = Field(default="", max_length=40)
    connection: str = Field(default="", max_length=12)


@router.post("/api/telemetry/vitals", status_code=204, dependencies=[Depends(limit_by_ip("vitals", 120, 60))])
def record_web_vital(payload: VitalPayload):
    """Velocidad medida en el navegador de usuarios reales (Core Web Vitals). Solo se registra en logs."""
    vitals_logger.info(
        "web-vital name=%s value=%.1f rating=%s page=%s connection=%s",
        payload.name, payload.value, payload.rating or "-", payload.page or "-", payload.connection or "-",
    )
    return Response(status_code=204)
