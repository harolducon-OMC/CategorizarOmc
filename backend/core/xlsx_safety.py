# -*- coding: utf-8 -*-
"""Seguridad de los libros de Excel que genera la plataforma.

Los textos de una encuesta, los nombres de marca y las respuestas abiertas los escriben personas. openpyxl guarda
como FÓRMULA cualquier texto que empiece con "=", así que una respuesta como «=HYPERLINK(...)» se ejecutaría al
abrir el archivo (inyección de fórmulas). Las funciones de este módulo lo evitan.
"""
from typing import Any

FORMULA_DATA_TYPE = "f"
TEXT_DATA_TYPE = "s"


def neutralize_formulas(workbook) -> int:
    """Convierte en texto toda celda que openpyxl iba a guardar como fórmula. Devuelve cuántas cambió.

    La plataforma nunca escribe fórmulas a propósito, por eso es seguro tratarlas todas como texto.
    No sirve para libros en modo write_only (no conservan las celdas): allí se usa safe_text().
    """
    changed = 0
    for sheet in workbook.worksheets:
        cells = getattr(sheet, "_cells", None)  # solo celdas con contenido (iter_rows recorre también las vacías)
        iterator = cells.values() if cells is not None else (cell for row in sheet.iter_rows() for cell in row)
        for cell in iterator:
            if cell.data_type == FORMULA_DATA_TYPE:
                cell.data_type = TEXT_DATA_TYPE
                changed += 1
    return changed


def safe_text(value: Any) -> Any:
    """Para escrituras en write_only: un texto que empiece con "=" lleva un apóstrofo delante para que sea texto."""
    if isinstance(value, str) and value.startswith("="):
        return "'" + value
    return value
