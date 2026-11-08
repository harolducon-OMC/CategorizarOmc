"""Políticas de seguridad de la plataforma, editables por los administradores.

Se guardan en la tabla `security_policies` (una fila). Si no hay nada guardado —o la base no responde—
se usan los valores por defecto, que equivalen al comportamiento anterior.
"""
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core import privacy
from core.llm import PROVIDER_CONFIG

logger = logging.getLogger(__name__)

POLICY_FIELDS = {
    # clave: (tipo, mínimo, máximo, descripción)
    "min_password_length": ("int", 12, 64, "Longitud mínima de contraseña (nuevas contraseñas)"),
    "require_complexity": ("bool", None, None, "Exigir mayúscula, minúscula, número y símbolo"),
    "session_minutes": ("int", 15, 1440, "Duración de la sesión en minutos (aplica a nuevos inicios de sesión)"),
    "max_failed_logins": ("int", 3, 20, "Intentos fallidos antes de bloquear la cuenta"),
    "lockout_minutes": ("int", 1, 1440, "Minutos de bloqueo tras superar los intentos fallidos"),
    "registration_enabled": ("bool", None, None, "Permitir que personas nuevas se registren"),
    "allowed_email_domains": ("domains", None, None, "Dominios de correo permitidos para registrarse (vacío = el configurado en el servidor)"),
    "ai_redact_pii": ("bool", None, None, "Ocultar correos, teléfonos y documentos antes de enviar texto a la IA"),
    "allowed_ai_providers": ("providers", None, None, "Proveedores de IA permitidos (vacío = todos)"),
}

_DOMAIN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$")


def default_policy() -> Dict:
    return {
        "min_password_length": 12, "require_complexity": False,
        "session_minutes": int(os.getenv("ACCESS_TOKEN_MINUTES", "60")),
        "max_failed_logins": 8, "lockout_minutes": 5, "registration_enabled": True,
        "allowed_email_domains": [], "ai_redact_pii": True, "allowed_ai_providers": [],
    }


def clean_policy(raw: Dict) -> Dict:
    """Valida los cambios recibidos. Devuelve solo claves conocidas; lanza ValueError con todos los problemas."""
    if not isinstance(raw, dict):
        raise ValueError("Formato de políticas no válido.")
    cleaned, problems = {}, []
    for key, value in raw.items():
        if key not in POLICY_FIELDS:
            problems.append(f"Política desconocida: {key}")
            continue
        kind, low, high, label = POLICY_FIELDS[key]
        if kind == "bool":
            if isinstance(value, bool):
                cleaned[key] = value
            else:
                problems.append(f"{label}: debe ser verdadero o falso")
        elif kind == "int":
            if isinstance(value, bool) or not isinstance(value, int) or not (low <= value <= high):
                problems.append(f"{label}: debe ser un número entre {low} y {high}")
            else:
                cleaned[key] = value
        elif kind == "domains":
            items = [str(item).strip().lower().lstrip("@").lstrip(".") for item in (value or [])] if isinstance(value, list) else None
            if items is None or len(items) > 20 or any(not _DOMAIN.match(item) for item in items):
                problems.append(f"{label}: usa dominios válidos como empresa.com (máximo 20)")
            else:
                cleaned[key] = list(dict.fromkeys(item for item in items if item))
        elif kind == "providers":
            items = [str(item).strip() for item in value] if isinstance(value, list) else None
            if items is None or any(item not in PROVIDER_CONFIG for item in items):
                problems.append(f"{label}: contiene proveedores no reconocidos")
            else:
                cleaned[key] = list(dict.fromkeys(items))
    if problems:
        raise ValueError("; ".join(problems))
    return cleaned


def password_problems(password: str, policy: Dict) -> List[str]:
    problems = []
    if len(password) < policy["min_password_length"]:
        problems.append(f"La contraseña debe tener al menos {policy['min_password_length']} caracteres.")
    if policy["require_complexity"]:
        checks = [(r"[A-ZÁÉÍÓÚÑ]", "una mayúscula"), (r"[a-záéíóúñ]", "una minúscula"), (r"\d", "un número"), (r"[^\w\s]|_", "un símbolo")]
        missing = [label for pattern, label in checks if not re.search(pattern, password)]
        if missing:
            problems.append("La contraseña debe incluir " + ", ".join(missing) + ".")
    return problems


def generate_temporary_password(length: int = 16) -> str:
    """Contraseña temporal aleatoria (sin caracteres ambiguos) con mayúscula, minúscula, número y símbolo."""
    groups = ["ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnpqrstuvwxyz", "23456789", "!@#$%*+-?"]
    chars = [secrets.choice(group) for group in groups]
    pool = "".join(groups)
    chars += [secrets.choice(pool) for _ in range(max(length, 12) - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def email_domain_ok(email: str, policy: Dict) -> bool:
    domains = policy.get("allowed_email_domains") or []
    if not domains:
        from .security import email_is_allowed  # dominio configurado en el servidor
        return email_is_allowed(email)
    return any(email.strip().lower().endswith("@" + domain) for domain in domains)


def provider_allowed(provider: str, policy: Optional[Dict] = None) -> bool:
    allowed = (policy or get_policy()).get("allowed_ai_providers") or []
    return not allowed or provider in allowed


# ---------------------------------------------------------------- almacenamiento con caché corta
_lock = threading.Lock()
_cache: Dict = {"value": None, "stored": {}, "expires": 0.0}
CACHE_SECONDS = 15


def _load_stored() -> Dict:
    from .auth_models import SecurityPolicy
    from .db import SessionLocal
    with SessionLocal() as db:
        row = db.get(SecurityPolicy, 1)
        return dict(row.values) if row is not None and row.values else {}


def get_policy() -> Dict:
    now = time.monotonic()
    with _lock:
        if _cache["value"] is not None and _cache["expires"] > now:
            return dict(_cache["value"])
    try:
        stored = _load_stored()
    except Exception:
        logger.warning("No se pudieron leer las políticas de seguridad; se usan los valores por defecto.", exc_info=True)
        stored = {}
    merged = {**default_policy(), **{key: value for key, value in stored.items() if key in POLICY_FIELDS}}
    with _lock:
        _cache.update(value=merged, stored=stored, expires=now + CACHE_SECONDS)
    privacy.set_override(stored.get("ai_redact_pii"))
    return dict(merged)


def invalidate() -> None:
    with _lock:
        _cache.update(value=None, expires=0.0)


def save_policy(db, updates: Dict, actor_email: str) -> Dict:
    """Guarda cambios ya validados (clean_policy) y devuelve la política vigente."""
    from .auth_models import SecurityPolicy
    row = db.get(SecurityPolicy, 1)
    if row is None:
        row = SecurityPolicy(id=1, values={})
        db.add(row)
    row.values = {**(row.values or {}), **updates}
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = actor_email
    db.flush()
    invalidate()
    return {**default_policy(), **row.values}
