"""Cachés de la API.

- TTLCache: en memoria (LRU con caducidad). Sirve para DataFrames de estudios.
- ResultCache: resultados ya calculados (frecuencias, segmentos). Usa Redis si defines
  REDIS_URL y la librería `redis` está instalada; si no, memoria del propio proceso.
  Si Redis falla, la API sigue funcionando (simplemente recalcula).
"""
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

logger = logging.getLogger(__name__)
MISSING = object()


class TTLCache:
    def __init__(self, max_entries: int = 128, ttl: float = 300.0, clock: Callable[[], float] = time.monotonic):
        self.max_entries, self.ttl, self._clock = max_entries, ttl, clock
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return MISSING
            expires, value = entry
            if expires <= self._clock():
                del self._data[key]
                return MISSING
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._data[key] = (self._clock() + (self.ttl if ttl is None else ttl), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class ResultCache:
    PREFIX = "insights:v1:"

    def __init__(self):
        self._memory = TTLCache(max_entries=512, ttl=600)
        self._redis = None
        self._redis_retry_at = 0.0
        url = os.getenv("REDIS_URL", "").strip()
        if url:
            try:
                import redis

                self._redis = redis.Redis.from_url(
                    url, socket_timeout=1.5, socket_connect_timeout=1.5, decode_responses=True,
                )
            except Exception as exc:  # librería ausente o URL inválida
                logger.warning("Redis no disponible, se usa caché en memoria: %s", exc)

    def _redis_ok(self) -> bool:
        return self._redis is not None and time.monotonic() >= self._redis_retry_at

    def _redis_failed(self, exc: Exception) -> None:
        logger.warning("Redis falló; se recalcula sin caché durante 30 s: %s", exc)
        self._redis_retry_at = time.monotonic() + 30

    def get(self, key: str) -> Any:
        if self._redis_ok():
            try:
                raw = self._redis.get(self.PREFIX + key)
                return MISSING if raw is None else json.loads(raw)
            except Exception as exc:
                self._redis_failed(exc)
        return self._memory.get(key)

    def set(self, key: str, value: Any, ttl: int = 600) -> None:
        if self._redis_ok():
            try:
                self._redis.set(self.PREFIX + key, json.dumps(value, default=str), ex=ttl)
                return
            except Exception as exc:
                self._redis_failed(exc)
        self._memory.set(key, value, ttl)

    def get_or_build(self, key: str, ttl: int, builder: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not MISSING:
            return cached
        value = builder()
        self.set(key, value, ttl)
        return value


frame_cache = TTLCache(max_entries=3, ttl=900)   # DataFrames de estudios abiertos recientemente
MAX_CACHED_CELLS = 1_500_000                       # no se cachean estudios gigantes (memoria)
result_cache = ResultCache()
