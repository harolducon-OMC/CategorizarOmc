# -*- coding: utf-8 -*-
"""Protección contra inyección de fórmulas en los Excel exportados.

Las respuestas de una encuesta las escriben terceros. Si una celda empieza por «=», openpyxl la guarda como
FÓRMULA y Excel la ejecutaría al abrir el archivo (p. ej. =HYPERLINK(...) o llamadas a otros libros).
Estas utilidades fuerzan que ese contenido se guarde siempre como TEXTO, sin alterar lo que se ve.
"""
import re
from typing import Any

# Caracteres de control que openpyxl rechaza en XML (IllegalCharacterError)
ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MAX_CELL_CHARS = 32767


def clean_text(value: str) -> str:
    return ILLEGAL_XML.sub("", value)[:MAX_CELL_CHARS]


def force_text_if_formula(cell) -> None:
    """Si openpyxl interpretó el valor como fórmula, lo vuelve texto literal."""
    if getattr(cell, "data_type", None) == "f":
        cell.data_type = "s"


def set_cell_value(cell, value: Any):
    """Asigna un valor a una celda sin permitir que un texto se convierta en fórmula."""
    if isinstance(value, str):
        value = clean_text(value)
    cell.value = value
    force_text_if_formula(cell)
    return cell
