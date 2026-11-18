"""Punto de entrada de la API: middleware, CORS y registro de routers.

Las rutas viven en app/routers/ (auth, system, studies, classifications,
study_awareness) y en app/awareness_flex.py (Awareness independiente).
"""
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # lee el .env de la raíz también cuando Uvicorn se lanza desde backend/
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import accounts, policies
from .awareness_flex import router as awareness_flex_router
from .common import _class_or_404, _labels_without_blank_responses, get_current_user_id  # noqa: F401  (compatibilidad con pruebas e importaciones previas)
from .db import Base, SessionLocal, engine
from .observability import init_sentry, init_tracing, request_id_ctx, setup_logging
from .routers import admin, auth, classifications, study_awareness, studies, system
from .security import token_claims, validate_security_config

setup_logging()
init_sentry()
logger = logging.getLogger("insights.api")
SLOW_REQUEST_SECONDS = float(os.getenv("SLOW_REQUEST_SECONDS", "5"))
PASSWORD_CHANGE_PATHS = {"/api/auth/change-password", "/api/auth/me"}
_REQUEST_ID_OK = re.compile(r"[A-Za-z0-9._-]{1,64}")
DOCS_PREFIXES = ("/docs", "/openapi.json", "/redoc")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_platform()
    yield


# DISABLE_API_DOCS=1 oculta /docs, /redoc y /openapi.json (recomendado en producción: no exponen el mapa de la API).
_DOCS_OFF = os.getenv("DISABLE_API_DOCS", "").strip().lower() in {"1", "true", "yes", "si", "sí"}
app = FastAPI(
    title="Plataforma de Insights API", version="1.0.0", lifespan=lifespan,
    docs_url=None if _DOCS_OFF else "/docs", redoc_url=None if _DOCS_OFF else "/redoc",
    openapi_url=None if _DOCS_OFF else "/openapi.json",
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    # El identificador entra a los logs: solo se acepta si es «seguro»; si no, se genera uno nuevo
    request_id = supplied_id if _REQUEST_ID_OK.fullmatch(supplied_id) else uuid.uuid4().hex[:12]
    request_id_ctx.set(request_id)
    started = time.monotonic()
    path = request.url.path
    public = path in {"/api/health", "/api/auth/register", "/api/auth/login", "/api/telemetry/vitals"} or path.startswith(DOCS_PREFIXES)
    if path.startswith("/api/") and request.method != "OPTIONS" and not public:
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        claims = token_claims(token) if scheme.lower() == "bearer" else None
        denied = lambda status_code, detail, code=None: JSONResponse(  # noqa: E731
            {"detail": detail, **({"code": code} if code else {})}, status_code=status_code, headers={"X-Request-ID": request_id})
        if not claims:
            return denied(401, "Se requiere un token de acceso válido.")
        # Cada petición valida el estado actual de la cuenta (caché corta): banear o inactivar surte efecto casi de inmediato
        status = await run_in_threadpool(accounts.account_status, claims["sub"])
        if status is None:
            return denied(401, "La sesión no corresponde a un usuario activo.", "session_invalid")
        if int(claims.get("tv", 0)) != status["token_version"]:
            return denied(401, "Tu sesión ya no es válida. Inicia sesión de nuevo.", "session_invalid")
        if status["banned"]:
            return denied(403, "Tu cuenta está suspendida por incumplir las políticas de la plataforma. Contacta al administrador.", "account_banned")
        if not status["active"]:
            return denied(403, "Tu cuenta está inactiva. Contacta al administrador.", "account_inactive")
        if status["must_change_password"] and path not in PASSWORD_CHANGE_PATHS:
            return denied(403, "Debes cambiar tu contraseña temporal antes de continuar.", "password_change_required")
        request.state.user_email = claims["sub"]
        request.state.user_role = status["role"]
        request.state.must_change_password = status["must_change_password"]
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
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if not path.startswith(DOCS_PREFIXES):  # Swagger/ReDoc necesitan scripts propios; la API JSON no necesita ninguno
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store" if path.startswith("/api/auth") or path.startswith("/api/me") else "no-cache"
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    request_id = request_id_ctx.get()
    return JSONResponse(
        {"detail": "Ocurrió un error interno. Si persiste, comparte este código con soporte.", "request_id": request_id},
        status_code=500, headers={"X-Request-ID": request_id},
    )


init_tracing(app, engine)
app.include_router(awareness_flex_router)
for _router_module in (auth, admin, system, studies, classifications, study_awareness):
    app.include_router(_router_module.router)


CORS_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
if "*" in CORS_ORIGINS:  # con credenciales, «*» permitiría que cualquier sitio use la sesión del usuario
    raise RuntimeError("CORS_ORIGINS no puede contener «*». Lista los orígenes exactos del frontend.")

# Comprime respuestas JSON grandes (los .xlsx y el streaming de IA se envían con Content-Encoding: identity)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-LLM-API-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Content-Disposition", "Retry-After"],
)


def initialize_platform():
    """Validación de seguridad, tablas, super administrador y políticas (se ejecuta al arrancar la API)."""
    validate_security_config()
    if os.getenv("AUTO_CREATE_TABLES", "1") != "0":
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            accounts.ensure_schema(connection)  # columnas nuevas de «users» en bases que ya existían
    try:
        with SessionLocal() as db:
            accounts.ensure_super_admin(db)
        policies.get_policy()  # carga las políticas y aplica las que afectan al motor de IA
    except Exception:
        logger.exception("No se pudo completar la inicialización de cuentas y políticas")
