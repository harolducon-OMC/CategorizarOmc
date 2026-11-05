"""Límite de peticiones en memoria (ventana deslizante).

Protege el login y los endpoints que consumen IA o mucho CPU. Es por proceso:
con una sola instancia en Render (plan actual) es suficiente. Si algún día se
escala a varias instancias, cambia el almacenamiento por Redis.

Variables de entorno:
  RATE_LIMIT_DISABLED=1   desactiva todos los límites (útil en pruebas locales).
"""
import math
import os
import threading
import time
from collections import deque
from typing import Callable, Deque, Dict, Tuple


def rate_limit_enabled() -> bool:
    return os.getenv("RATE_LIMIT_DISABLED", "").strip().lower() not in {"1", "true", "yes", "si", "sí"}


class SlidingWindowLimiter:
    """Cuenta eventos por clave dentro de una ventana de tiempo móvil."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = {}
        self._windows: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def check(self, key: str, limit: int, window: float) -> Tuple[bool, int]:
        """Devuelve (permitido, segundos_para_reintentar). Registra el intento si se permite."""
        now = self._clock()
        with self._lock:
            self._calls += 1
            if self._calls % 500 == 0:
                self._purge(now)
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits
            self._windows[key] = window
            cutoff = now - window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, math.ceil(hits[0] + window - now))
                return False, retry_after
            hits.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._windows.clear()

    def _purge(self, now: float) -> None:
        for key in list(self._hits):
            hits = self._hits[key]
            window = self._windows.get(key, 0)
            if not hits or hits[-1] <= now - window:
                self._hits.pop(key, None)
                self._windows.pop(key, None)


limiter = SlidingWindowLimiter()


def client_ip(request) -> str:
    """IP del cliente. Detrás de Vercel/Render se toma la primera de X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip() if forwarded else ""
    if first:
        return first
    return request.client.host if getattr(request, "client", None) else "desconocido"


def enforce(name: str, key: str, limit: int, window: float) -> None:
    """Lanza HTTP 429 si la clave superó el límite. No hace nada si está desactivado."""
    if not rate_limit_enabled():
        return
    allowed, retry_after = limiter.check(f"{name}:{key}", limit, window)
    if not allowed:
        from fastapi import HTTPException

        raise HTTPException(
            429,
            f"Demasiadas solicitudes. Intenta de nuevo en {retry_after} s.",
            headers={"Retry-After": str(retry_after)},
        )


def limit_by_ip(name: str, limit: int, window: float):
    """Dependencia de FastAPI: límite por IP (para rutas públicas como login)."""
    from fastapi import Request

    def dependency(request: Request) -> None:
        enforce(name, client_ip(request), limit, window)

    return dependency


def limit_by_user(name: str, limit: int, window: float):
    """Dependencia de FastAPI: límite por usuario autenticado (cae a la IP si no hay sesión)."""
    from fastapi import Request

    def dependency(request: Request) -> None:
        identity = getattr(request.state, "user_email", None) or client_ip(request)
        enforce(name, str(identity).lower(), limit, window)

    return dependency
