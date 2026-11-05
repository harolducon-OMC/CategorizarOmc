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


def init_tracing(app, engine=None) -> bool:
    """Trazas con OpenTelemetry (peticiones y consultas SQL lentas). Opcional.

    Se activa solo si defines OTEL_EXPORTER_OTLP_ENDPOINT (y OTEL_EXPORTER_OTLP_HEADERS si tu
    proveedor lo pide, p. ej. Grafana Cloud o Honeycomb) y se instalaron las librerías de
    requirements-optional.txt.
    """
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        return False
    log = logging.getLogger(__name__)
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("OTEL_EXPORTER_OTLP_ENDPOINT definido pero faltan librerías: pip install -r requirements-optional.txt")
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "insights-api")}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # lee endpoint y cabeceras de las variables OTEL_*
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="api/health,api/telemetry")
    if engine is not None:
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            SQLAlchemyInstrumentor().instrument(engine=engine)
        except ImportError:
            log.info("Sin instrumentación de SQLAlchemy; solo se trazan las peticiones.")
    return True
