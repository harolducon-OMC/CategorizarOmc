# -*- coding: utf-8 -*-
"""
core/awareness_flex.py
Awareness INDEPENDIENTE (carga de CSV/Excel sin estudio ni categorización).

Es la versión web del "Generador flexible de Awareness / Recordación"
(streamlit_awareness_generico.py). Reutiliza core/awareness.py sin modificarlo,
así el cálculo es idéntico al del flujo integrado y al de la app Streamlit original.
Este módulo no depende de FastAPI ni de la base de datos para poder probarse solo.
"""

import json
from typing import Any, Dict, List

import pandas as pd

from . import awareness

DEMO_KEYS = ["sexo", "edad", "departamento", "estrato", "ingreso"]


def presets() -> Dict[str, Dict[str, Any]]:
    """Mismos presets que la app Streamlit (Bancos, Conglomerados, Personalizado)."""
    return {
        "bancos": {
            "label": "Bancos",
            "entities": awareness.BANKS,
            "aliases": awareness.BANK_ALIASES,
            "normalizations": awareness.BANK_NORMALIZATIONS,
            "demographics": {"sexo": "F1 ", "edad": "F2 ", "departamento": "F4 ", "estrato": "F3 ", "ingreso": "0"},
            "analyses": [
                {"name": "AWA PUB", "tom": "0", "esp": "0", "ayu": "0"},
                {"name": "AWA Marca", "tom": "P1", "esp": "P1A.1\nP1A.2\nP1A.3", "ayu": "P2.1\nP2.2\nP2.3"},
            ],
            "expected_raw_cols": 17,
        },
        "conglomerados": {
            "label": "Conglomerados Financieros",
            "entities": awareness.CONGLOMERATES,
            "aliases": awareness.CONGLOMERATE_ALIASES,
            "normalizations": awareness.CONGLOMERATE_NORMALIZATIONS,
            "demographics": {"sexo": "F1", "edad": "F2a", "departamento": "F4", "estrato": "F3", "ingreso": "F5"},
            "analyses": [
                {"name": "Desactivado", "tom": "0", "esp": "0", "ayu": "0"},
                {"name": "Conglomerados AWA", "tom": "P1 -", "esp": "P1A -", "ayu": "P2-P2."},
            ],
            "expected_raw_cols": 0,
        },
        "personalizado": {
            "label": "Personalizado",
            "entities": ["Marca 1", "Marca 2"],
            "aliases": {"Marca 1": ["marca 1", "m1"], "Marca 2": ["marca 2", "m2"]},
            "normalizations": [],
            "demographics": {key: "" for key in DEMO_KEYS},
            "analyses": [
                {"name": "Análisis 1", "tom": "0", "esp": "0", "ayu": "0"},
                {"name": "Análisis 2", "tom": "0", "esp": "0", "ayu": "0"},
            ],
            "expected_raw_cols": 0,
        },
    }


def parse_config(raw) -> Dict[str, Any]:
    """Convierte y valida la configuración enviada por la interfaz."""
    data = json.loads(raw) if isinstance(raw, (str, bytes)) else dict(raw or {})
    entities = [str(item).strip() for item in data.get("entities", []) if str(item).strip()]
    if not entities:
        raise ValueError("Escribe al menos una entidad / marca a evaluar.")
    aliases = data.get("aliases") or {}
    normalizations = data.get("normalizations") or []
    if not isinstance(aliases, dict):
        raise ValueError("Los alias deben ser un objeto JSON {\"Marca\": [\"alias\", ...]}.")
    if not isinstance(normalizations, list):
        raise ValueError("Las normalizaciones deben ser una lista JSON.")
    demographics = {key: str((data.get("demographics") or {}).get(key, "") or "") for key in DEMO_KEYS}
    analyses = []
    for index, item in enumerate((data.get("analyses") or [])[:2], start=1):
        analyses.append({
            "name": str(item.get("name") or f"Análisis {index}").strip() or f"Análisis {index}",
            "tom": str(item.get("tom") or "0"),
            "esp": str(item.get("esp") or "0"),
            "ayu": str(item.get("ayu") or "0"),
        })
    while len(analyses) < 2:
        analyses.append({"name": f"Análisis {len(analyses) + 1}", "tom": "0", "esp": "0", "ayu": "0"})
    return {
        "entities": entities, "aliases": aliases, "normalizations": normalizations,
        "demographics": demographics, "analyses": analyses,
        "max_rows": max(int(data.get("max_rows") or 0), 0),
        "expected_raw_cols": max(int(data.get("expected_raw_cols") or 0), 0),
    }


def _active(cfg: Dict[str, str]) -> bool:
    return any(str(cfg[key]).strip() not in ("0", "") for key in ("tom", "esp", "ayu"))


def detect_columns(columns: List[str], config: Dict[str, Any]) -> List[Dict[str, str]]:
    """Tabla de 'Validación de columnas': qué columna detecta cada prefijo."""
    frame = pd.DataFrame(columns=list(columns))
    rows = []
    for key in DEMO_KEYS:
        found = awareness.find_col(frame, config["demographics"].get(key, ""))
        rows.append({"tipo": "Demográfico", "campo": key, "columnas": str(found) if found else ""})
    for index, cfg in enumerate(config["analyses"], start=1):
        if not _active(cfg):
            continue
        label = f"Análisis {index} · {cfg['name']}"
        tom = awareness.find_col(frame, cfg["tom"])
        rows.append({"tipo": label, "campo": "TOM", "columnas": str(tom) if tom else ""})
        rows.append({"tipo": label, "campo": "Espontáneo", "columnas": ", ".join(map(str, awareness.find_cols(frame, cfg["esp"])))})
        rows.append({"tipo": label, "campo": "Ayudado", "columnas": ", ".join(map(str, awareness.find_cols(frame, cfg["ayu"])))})
    return rows


def generate_report(frame: pd.DataFrame, config: Dict[str, Any]) -> bytes:
    """Excel final idéntico al de la app Streamlit original."""
    if config["max_rows"]:
        frame = frame.head(config["max_rows"]).copy()
    demo_cols = {key: awareness.find_col(frame, config["demographics"].get(key, "")) for key in DEMO_KEYS}
    cfg1, cfg2 = config["analyses"]
    return awareness.build_excel_bytes(
        frame, demo_cols, cfg1, cfg2, config["entities"], config["aliases"],
        config["normalizations"], config["expected_raw_cols"],
    )
