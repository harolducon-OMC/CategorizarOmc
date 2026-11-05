"""Logging estructurado con identificador por petición y Sentry opcional."""
import contextvars
import logging
import os
import sys

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SENSITIVE_HEADERS = {"authorization", "x-llm-api-key", "cookie", "x-api-key"}


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def setup_logging() -> None:
    """Configura el log raíz una sola vez (también con uvicorn --reload)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_insights_handler", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler._insights_handler = True  # type: ignore[attr-defined]
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def scrub_event(event: dict, hint=None):
    """Quita tokens y claves de IA antes de enviar un evento a Sentry."""
    request = event.get("request") or {}
    headers = request.get("headers")
    if isinstance(headers, dict):
        for name in list(headers):
            if name.lower() in _SENSITIVE_HEADERS:
                headers[name] = "[Filtered]"
    request.pop("data", None)  # nunca enviar cuerpos (pueden traer contraseñas o respuestas de encuestas)
    return event


def init_sentry() -> bool:
    """Activa Sentry solo si SENTRY_DSN está definido y sentry-sdk instalado."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger(__name__).warning("SENTRY_DSN definido pero sentry-sdk no está instalado.")
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
        before_send=scrub_event,
    )
    return True
