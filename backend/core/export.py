# -*- coding: utf-8 -*-
"""
core/export.py
Exportación a Excel de las categorizaciones de un estudio (datos, preguntas con categorías y diccionario).
"""

import io
from typing import Dict

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill

from core.awareness import safe_sheet_name
from core.xlsafe import ILLEGAL_XML, force_text_if_formula

_ILLEGAL = ILLEGAL_XML


def build_study_categorization_excel(df: pd.DataFrame, classifications: list[Dict]) -> bytes:
    """Exporta tres hojas limpias y evita asignar etiquetas a respuestas vacías."""
    from openpyxl.utils import get_column_letter
    from core.coding import is_blank_response

    wb = Workbook(write_only=True)

    def safe_value(value):
        if value is None:
            return None
        if hasattr(value, "item"):
            try:
                value = value.item()
            except (ValueError, AttributeError):
                pass
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(value, str):
            if not value.strip():
                return None
            return _ILLEGAL.sub("", value)[:32767]
        return value

    def text_row(ws, values):
        """Agrega una fila; cualquier texto que empiece por «=» queda como texto, nunca como fórmula."""
        cells = []
        for value in values:
            if isinstance(value, str):
                cell = WriteOnlyCell(ws, value=value)
                force_text_if_formula(cell)
                cells.append(cell)
            else:
                cells.append(value)
        ws.append(cells)

    def append_header(ws, headers, widths=None):
        cells = []
        for value in headers:
            cell = WriteOnlyCell(ws, value=safe_value(str(value)))
            force_text_if_formula(cell)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="17365D")
            cells.append(cell)
        ws.append(cells)
        ws.freeze_panes = "A2"
        if widths:
            for index, width in enumerate(widths, start=1):
                ws.column_dimensions[get_column_letter(index)].width = width
        return len(headers)

    # Hoja 1: copia legible de los datos importados, sin columnas de resultados.
    data_ws = wb.create_sheet(safe_sheet_name("Datos"))
    data_columns = [str(column) for column in df.columns]
    data_count = append_header(data_ws, data_columns, [22] * len(data_columns))
    for row in df.itertuples(index=False, name=None):
        text_row(data_ws, [safe_value(value) for value in row])
    if data_count:
        data_ws.auto_filter.ref = f"A1:{get_column_letter(data_count)}{len(df) + 1}"

    # Hoja 2: una pareja respuesta/categoría por pregunta y por persona.
    result_ws = wb.create_sheet(safe_sheet_name("Preguntas y categorización"))
    result_headers = ["Fila de encuesta"]
    widths = [16]
    for item in classifications:
        question = str(item.get("question", "Pregunta"))
        result_headers.extend([f"{question} | Respuesta", f"{question} | Categoría(s)"])
        widths.extend([42, 30])
    result_count = append_header(result_ws, result_headers, widths)
    columns = list(df.columns)
    responses_by_question = {
        item.get("question", ""): df[item.get("question")].tolist() if item.get("question") in columns else [None] * len(df)
        for item in classifications
    }
    for row_index in range(len(df)):
        values = [row_index + 2]  # fila equivalente en la hoja Datos (encabezado en fila 1)
        for item in classifications:
            question = item.get("question", "")
            response = responses_by_question[question][row_index]
            saved_labels = item.get("labels") or []
            labels = saved_labels[row_index] if row_index < len(saved_labels) else []
            if is_blank_response(response):
                values.extend([None, None])
            else:
                values.extend([safe_value(response), safe_value(" | ".join(str(label) for label in (labels or [])))])
        text_row(result_ws, values)
    if result_count:
        result_ws.auto_filter.ref = f"A1:{get_column_letter(result_count)}{len(df) + 1}"

    # Hoja 3: codebook, sin repetir categorías, términos ni alias.
    dictionary_ws = wb.create_sheet(safe_sheet_name("Diccionario"))
    dictionary_headers = ["Pregunta", "Tipo de análisis", "Código / categoría", "Descripción", "Palabras clave / sinónimos", "Alias / variantes"]
    dictionary_count = append_header(dictionary_ws, dictionary_headers, [24, 20, 30, 62, 42, 42])
    kind_names = {"brands": "Marcas", "sentiment": "Sentimiento", "themes": "Temas"}
    dictionary_rows = 1
    for item in classifications:
        question = str(item.get("question", ""))
        kind = str(item.get("kind", ""))
        kind_label = kind_names.get(kind, kind)
        frame = [entry for entry in (item.get("codeframe") or []) if isinstance(entry, dict)]
        frame_by_name = {str(entry.get("nombre", "")): entry for entry in frame}
        config = item.get("config") or {}
        categories = list(item.get("categories") or [])
        if kind == "brands":
            categories = list(dict.fromkeys([*(config.get("known_brands") or []), *categories, "Otra", "Ninguna", "NS/NR"]))
        else:
            categories = list(dict.fromkeys([*categories, "Otros", "NS/NR"]))
        brand_mapping = item.get("brand_mapping") or {}
        for category in categories:
            name = str(category)
            entry = frame_by_name.get(name, {})
            keywords = entry.get("palabras_clave", entry.get("sinonimos", []))
            if isinstance(keywords, list):
                keywords = ", ".join(str(value) for value in keywords)
            aliases = []
            if kind == "brands":
                aliases = [str(raw) for raw, canonical in brand_mapping.items() if str(canonical) == name and str(raw) != name]
                if not aliases:
                    aliases = (item.get("aliases") or {}).get(name, [])
            description = entry.get("descripcion", "")
            if not description:
                description = {
                    "Otra": "Mención de marca fuera del catálogo permitido.",
                    "Ninguna": "Respuesta explícita que indica que no menciona una marca.",
                    "Otros": "Respuesta válida que no encaja en las categorías definidas.",
                    "NS/NR": "Respuesta explícita sin información; una celda vacía permanece en blanco.",
                }.get(name, "Marca del catálogo permitido." if kind == "brands" else "")
            text_row(dictionary_ws, [
                safe_value(question), kind_label, safe_value(name), safe_value(description),
                safe_value(str(keywords or "")), safe_value(" | ".join(str(value) for value in aliases)),
            ])
            dictionary_rows += 1
    if dictionary_count:
        dictionary_ws.auto_filter.ref = f"A1:{get_column_letter(dictionary_count)}{dictionary_rows}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
