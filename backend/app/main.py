"""Punto de entrada de la API: middleware, CORS y registro de routers.

Las rutas viven en app/routers/ (auth, system, studies, classifications,
study_awareness) y en app/awareness_flex.py (Awareness independiente).
"""
import logging
import os
import time
import uuid

from dotenv import load_dotenv
load_dotenv()  # lee el .env de la raíz también cuando Uvicorn se lanza desde backend/
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .awareness_flex import router as awareness_flex_router
from .common import _class_or_404, _labels_without_blank_responses, get_current_user_id  # noqa: F401  (compatibilidad con pruebas e importaciones previas)
from .db import Base, engine
from .observability import init_sentry, request_id_ctx, setup_logging
from .routers import auth, classifications, study_awareness, studies, system
from .security import token_subject, validate_security_config

setup_logging()
init_sentry()
logger = logging.getLogger("insights.api")
SLOW_REQUEST_SECONDS = float(os.getenv("SLOW_REQUEST_SECONDS", "5"))

app = FastAPI(title="Plataforma de Insights API", version="1.0.0")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request_id = (request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12])[:64]
    request_id_ctx.set(request_id)
    started = time.monotonic()
    path = request.url.path
    public = path in {"/api/health", "/api/auth/register", "/api/auth/login"} or path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc")
    if path.startswith("/api/") and request.method != "OPTIONS" and not public:
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        email = token_subject(token) if scheme.lower() == "bearer" else None
        if not email:
            return JSONResponse({"detail": "Se requiere un token de acceso válido."}, status_code=401, headers={"X-Request-ID": request_id})
        request.state.user_email = email
    response = await call_next(request)
    elapsed = time.monotonic() - started
    if response.status_code >= 500:
        logger.error("%s %s -> %s (%.2fs)", request.method, path, response.status_code, elapsed)
    elif elapsed >= SLOW_REQUEST_SECONDS:
        logger.warning("Petición lenta: %s %s -> %s (%.2fs)", request.method, path, response.status_code, elapsed)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store" if path.startswith("/api/auth") else "no-cache"
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    request_id = request_id_ctx.get()
    return JSONResponse(
        {"detail": "Ocurrió un error interno. Si persiste, comparte este código con soporte.", "request_id": request_id},
        status_code=500, headers={"X-Request-ID": request_id},
    )


app.include_router(awareness_flex_router)
for _router_module in (auth, system, studies, classifications, study_awareness):
    app.include_router(_router_module.router)


CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables():
    validate_security_config()
    if os.getenv("AUTO_CREATE_TABLES", "1") != "0":
        Base.metadata.create_all(bind=engine)
