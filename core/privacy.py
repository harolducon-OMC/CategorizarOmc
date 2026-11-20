# -*- coding: utf-8 -*-
"""Minimización de datos personales antes de enviar texto a un proveedor de IA.

Oculta correos, enlaces, tarjetas, celulares y números de documento (cédula, NIT) que las personas
a veces escriben en respuestas abiertas. Es una medida de minimización: no sustituye la autorización
de los titulares ni garantiza detectar nombres propios u otros datos.

Variable de entorno: AI_REDACT_PII=0 la desactiva (por defecto está activa).
"""
import os
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_MOBILE_CO = re.compile(r"(?<!\d)(?:\+?57[\s.-]?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
_LONG_ID = re.compile(r"(?<!\d)\d{1,3}(?:\.\d{3}){2,3}(?!\d)|(?<!\d)\d{8,12}(?!\d)")


_override = None  # lo fija la política de seguridad del panel de administración (None = usar la variable de entorno)


def set_override(value) -> None:
    global _override
    _override = None if value is None else bool(value)


def redact_enabled() -> bool:
    if _override is not None:
        return _override
    return os.getenv("AI_REDACT_PII", "1").strip().lower() not in {"0", "false", "no"}


def redact_pii(text: str) -> str:
    """Devuelve el texto con los datos personales más comunes reemplazados por marcadores."""
    if not text:
        return text
    text = _EMAIL.sub("[CORREO]", text)
    text = _URL.sub("[ENLACE]", text)
    text = _CARD.sub("[NUMERO]", text)
    text = _MOBILE_CO.sub("[TELEFONO]", text)
    text = _LONG_ID.sub("[DOCUMENTO]", text)
    return text
