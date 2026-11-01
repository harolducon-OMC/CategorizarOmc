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
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from . import awareness, brands

DEMO_KEYS = ["sexo", "edad", "departamento", "estrato", "ingreso"]
RESERVED_ENTITIES = {"ninguna", "ninguno", "ns nr", "nsnr", "ns", "nr", "otra", "otro", "no responde", "no sabe"}
FUZZY_THRESHOLD = 88   # similitud mínima (0-100) para agrupar una variante con una marca
FUZZY_MIN_LEN = 5      # por debajo de 5 letras solo se acepta coincidencia exacta (evita Puma = Pura)


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
    requested = [str(item).strip() for item in data.get("entities", []) if str(item).strip()]
    # "Ninguna", NS/NR u "Otra" no son marcas: nunca suman recordación, así que no se grafican.
    entities = [name for name in requested if awareness.norm(name) not in RESERVED_ENTITIES]
    ignored = [name for name in requested if name not in entities]
    if not entities:
        raise ValueError("Escribe al menos una marca real a evaluar (Ninguna, NS/NR y Otra no cuentan como marca).")
    aliases = data.get("aliases") or {}
    normalizations = data.get("normalizations") or []
    if not isinstance(aliases, dict):
        raise ValueError("Los alias deben ser un objeto JSON {\"Marca\": [\"alias\", ...]}.")
    if not isinstance(normalizations, list):
        raise ValueError("Las normalizaciones deben ser una lista JSON.")
    demographics = {key: str((data.get("demographics") or {}).get(key, "") or "") for key in DEMO_KEYS}
    tom_first_only = bool(data.get("tom_first_only", True))
    fuzzy = bool(data.get("fuzzy", True))
    analyses = []
    for index, item in enumerate((data.get("analyses") or [])[:2], start=1):
        analyses.append({
            "tom_first_only": tom_first_only,
            "name": str(item.get("name") or f"Análisis {index}").strip() or f"Análisis {index}",
            "tom": str(item.get("tom") or "0"),
            "esp": str(item.get("esp") or "0"),
            "ayu": str(item.get("ayu") or "0"),
        })
    while len(analyses) < 2:
        analyses.append({"tom_first_only": tom_first_only, "name": f"Análisis {len(analyses) + 1}", "tom": "0", "esp": "0", "ayu": "0"})
    return {
        "entities": entities, "ignored_entities": ignored, "fuzzy": fuzzy, "tom_first_only": tom_first_only,
        "aliases": aliases, "normalizations": normalizations,
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
        tom = awareness.find_cols(frame, cfg["tom"])
        rows.append({"tipo": label, "campo": "TOM", "columnas": ", ".join(map(str, tom))})
        rows.append({"tipo": label, "campo": "Espontáneo", "columnas": ", ".join(map(str, awareness.find_cols(frame, cfg["esp"])))})
        rows.append({"tipo": label, "campo": "Ayudado", "columnas": ", ".join(map(str, awareness.find_cols(frame, cfg["ayu"])))})
    return rows


def preview_results(frame: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """Return the same general Awareness tables used by the downloadable report."""
    if config["max_rows"]:
        frame = frame.head(config["max_rows"]).copy()

    active_analyses = [cfg for cfg in config["analyses"] if _active(cfg)]
    if not active_analyses:
        raise ValueError("Debe configurar al menos un análisis válido (TOM, Espontáneo o Ayudado).")

    demo_cols = {
        key: awareness.find_col(frame, config["demographics"].get(key, ""))
        for key in DEMO_KEYS
    }
    analyses = []
    for cfg in active_analyses:
        _, indicators, _ = awareness.build_analysis(
            frame, demo_cols, cfg, config["entities"], config["aliases"],
            config["normalizations"], config["expected_raw_cols"],
        )
        table = awareness.category_table(indicators, frame, None, None, config["entities"])
        rows = []
        for record in table.to_dict(orient="records"):
            rows.append({
                "Entidad": str(record["Entidad"]),
                "TOM": int(record["TOM"]),
                "TOM %": float(record["TOM %"]),
                "Espontaneo": int(record["Espontaneo"]),
                "Espontaneo %": float(record["Espontaneo %"]),
                "Ayudado": int(record["Ayudado"]),
                "Ayudado %": float(record["Ayudado %"]),
                "AWA": int(record["AWA"]),
                "AWA %": float(record["AWA %"]),
            })
        analyses.append({"name": cfg["name"], "rows": rows})

    return {"base": int(len(frame)), "analyses": analyses}


# ============================================================ agrupar variantes parecidas
def _pieces(value) -> List[str]:
    """Trozos de una celda: "Puma, Nike y Adidas" -> ["Puma", "Nike", "Adidas"]."""
    if pd.isna(value):
        return []
    text = str(value).strip()
    return [part.strip() for part in awareness._FIRST_MENTION_SPLIT.split(text) if part.strip()]


def _compact(text: str) -> str:
    return awareness.norm(text).replace(" ", "")


def _is_noise(piece: str) -> bool:
    key = awareness.norm(piece)
    return (not key) or key in awareness.NEGATIVOS or key in RESERVED_ENTITIES or key.replace(" ", "").isdigit()


def _text_columns(frame: pd.DataFrame, config: Dict[str, Any]) -> List[str]:
    """Columnas de respuesta abierta (TOM, espontáneo y ayudado) de los análisis activos."""
    columns: List[str] = []
    for cfg in config["analyses"]:
        if not _active(cfg):
            continue
        tom = awareness.find_col(frame, cfg["tom"])
        for column in ([tom] if tom else []) + awareness.find_cols(frame, cfg["esp"]) + awareness.find_cols(frame, cfg["ayu"]):
            if column not in columns:
                columns.append(column)
    return columns


def _observed(frame: pd.DataFrame, columns: List[str]) -> Tuple[Counter, Dict[str, Counter]]:
    """(conteo por forma normalizada, grafías originales vistas de cada forma)."""
    counts: Counter = Counter()
    spellings: Dict[str, Counter] = {}
    for column in columns:
        for value in frame[column].tolist():
            for piece in _pieces(value):
                if _is_noise(piece):
                    continue
                key = awareness.norm(piece)
                counts[key] += 1
                spellings.setdefault(key, Counter())[piece] += 1
    return counts, spellings


def learn_variants(frame: pd.DataFrame, config: Dict[str, Any]) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    """Agrega como alias las respuestas escritas parecido a una marca ("Decatlon" -> "Decathlon").

    Devuelve (alias completos, lista de variantes aprendidas para mostrar al usuario).
    """
    aliases = {entity: list(config["aliases"].get(entity) or [entity]) for entity in config["entities"]}
    if not config.get("fuzzy", True):
        return aliases, []
    counts, spellings = _observed(frame, _text_columns(frame, config))
    names = {entity: {awareness.norm(entity)} | {awareness.norm(a) for a in aliases[entity]} for entity in aliases}
    learned: List[Dict[str, Any]] = []
    for key, count in counts.most_common():
        compact = key.replace(" ", "")
        if len(compact) < FUZZY_MIN_LEN:
            continue
        if any(awareness.contains_entity(key, entity, aliases) for entity in aliases):
            continue  # ya la reconoce un alias exacto
        best, best_score = None, 0.0
        for entity, forms in names.items():
            for form in forms:
                form_compact = form.replace(" ", "")
                if len(form_compact) < FUZZY_MIN_LEN:
                    continue
                score = brands.similarity(compact, form_compact)
                if score > best_score:
                    best, best_score = entity, score
        if best is not None and best_score >= FUZZY_THRESHOLD:
            aliases[best].append(key)
            names[best].add(key)
            learned.append({"variante": spellings[key].most_common(1)[0][0], "marca": best, "n": int(count)})
    return aliases, learned


def suggest_entities(frame: pd.DataFrame, config: Dict[str, Any], limit: int = 30) -> Dict[str, Any]:
    """Propone la lista de marcas leyendo las respuestas, agrupando las escritas parecido."""
    columns = _text_columns(frame, config)
    if not columns:
        raise ValueError("No se detectó ninguna columna TOM, espontánea o ayudada con los prefijos indicados.")
    counts, spellings = _observed(frame, columns)
    if not counts:
        raise ValueError("Las columnas indicadas no tienen respuestas de marcas.")
    rows = [[spellings[key].most_common(1)[0][0]] for key, n in counts.items() for _ in range(n)]
    table = brands.build_mapping(rows, threshold=FUZZY_THRESHOLD)
    totals: Counter = Counter()
    variants: Dict[str, set] = {}
    for record in table.to_dict(orient="records"):
        canonical = str(record["Marca normalizada"])
        totals[canonical] += int(record["Menciones"])
        variants.setdefault(canonical, set()).update({awareness.norm(canonical), awareness.norm(record["Mención"])})
    chosen = [name for name, _ in totals.most_common(limit)]
    return {
        "entities": chosen,
        "aliases": {name: sorted(v for v in variants[name] if v) for name in chosen},
        "counts": {name: int(totals[name]) for name in chosen},
        "distinct": len(totals),
    }


# ============================================================ cálculo
def _prepare(frame: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]:
    if config["max_rows"]:
        frame = frame.head(config["max_rows"]).copy()
    aliases, learned = learn_variants(frame, config)
    return frame, {**config, "aliases": aliases}, learned


def _coverage(frame: pd.DataFrame, cfg: Dict[str, Any], indicators: pd.DataFrame, entities: List[str]) -> Optional[Dict[str, Any]]:
    """Qué parte de las respuestas reconoció la lista de marcas y cuáles quedaron sin reconocer."""
    tom_col = awareness.find_col(frame, cfg["tom"])
    esp_cols = awareness.find_cols(frame, cfg["esp"])
    column = tom_col or (esp_cols[0] if esp_cols else None)
    if column is None:
        return None
    kind = "TOM" if tom_col else "Espontaneo"
    hit = pd.Series(False, index=frame.index)
    for entity in entities:
        if (entity, kind) in indicators:
            hit = hit | (indicators[(entity, kind)] == 1)
        if kind == "Espontaneo" and (entity, "TOM") in indicators:
            hit = hit | (indicators[(entity, "TOM")] == 1)
    answered, missed, spellings = 0, Counter(), {}
    for position, value in zip(frame.index, frame[column].tolist()):
        pieces = [piece for piece in _pieces(value) if not _is_noise(piece)]
        if not pieces:
            continue
        answered += 1
        if hit[position]:
            continue
        piece = pieces[0]
        key = awareness.norm(piece)
        missed[key] += 1
        spellings.setdefault(key, Counter())[piece] += 1
    recognized = answered - sum(missed.values())
    return {
        "question": str(column), "role": "TOM" if tom_col else "Espontáneo",
        "answers": int(answered), "recognized": int(recognized),
        "unrecognized": [{"respuesta": spellings[key].most_common(1)[0][0], "n": int(n)} for key, n in missed.most_common(8)],
    }


def generate_report(frame: pd.DataFrame, config: Dict[str, Any]) -> bytes:
    """Excel final idéntico al de la app Streamlit original (con variantes parecidas agrupadas)."""
    frame, config, _ = _prepare(frame, config)
    demo_cols = {key: awareness.find_col(frame, config["demographics"].get(key, "")) for key in DEMO_KEYS}
    cfg1, cfg2 = config["analyses"]
    return awareness.build_excel_bytes(
        frame, demo_cols, cfg1, cfg2, config["entities"], config["aliases"],
        config["normalizations"], config["expected_raw_cols"],
    )


def preview_results(frame: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """Mismas tablas del reporte descargable + cobertura y variantes agrupadas."""
    frame, config, learned = _prepare(frame, config)
    active_analyses = [cfg for cfg in config["analyses"] if _active(cfg)]
    if not active_analyses:
        raise ValueError("Debe configurar al menos un análisis válido (TOM, Espontáneo o Ayudado).")

    demo_cols = {key: awareness.find_col(frame, config["demographics"].get(key, "")) for key in DEMO_KEYS}
    analyses = []
    for cfg in active_analyses:
        _, indicators, _ = awareness.build_analysis(
            frame, demo_cols, cfg, config["entities"], config["aliases"],
            config["normalizations"], config["expected_raw_cols"],
        )
        table = awareness.category_table(indicators, frame, None, None, config["entities"])
        rows = []
        for record in table.to_dict(orient="records"):
            rows.append({
                "Entidad": str(record["Entidad"]),
                "TOM": int(record["TOM"]), "TOM %": float(record["TOM %"]),
                "Espontaneo": int(record["Espontaneo"]), "Espontaneo %": float(record["Espontaneo %"]),
                "Ayudado": int(record["Ayudado"]), "Ayudado %": float(record["Ayudado %"]),
                "AWA": int(record["AWA"]), "AWA %": float(record["AWA %"]),
            })
        analyses.append({"name": cfg["name"], "rows": rows, "coverage": _coverage(frame, cfg, indicators, config["entities"])})

    return {
        "base": int(len(frame)), "analyses": analyses,
        "learned_variants": learned, "ignored_entities": config.get("ignored_entities", []),
    }
