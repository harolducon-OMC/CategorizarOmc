# -*- coding: utf-8 -*-
"""Calidad de la categorización: acuerdo entre las etiquetas de la IA y las revisadas por una persona.

Todo es cálculo determinista sobre una muestra revisada (no usa IA). Las métricas por categoría son
precisión, exhaustividad (recall) y F1 tratando la etiqueta humana como la referencia.
"""
import math
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

MIN_RELIABLE_SAMPLE = 50


def label_set(labels) -> frozenset:
    if labels is None:
        return frozenset()
    if isinstance(labels, str):
        labels = [labels]
    return frozenset(str(label).strip() for label in labels if label is not None and str(label).strip())


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Intervalo de confianza (95 %) para una proporción; útil con muestras pequeñas."""
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _ratio(numerator: float, denominator: float) -> Optional[float]:
    return numerator / denominator if denominator else None


def _f1(tp: int, fp: int, fn: int) -> Optional[float]:
    """F1 = 2TP / (2TP + FP + FN); es 0 cuando la categoría existe pero nunca se acierta."""
    denominator = 2 * tp + fp + fn
    return 2 * tp / denominator if denominator else None


def cohen_kappa(pairs: Sequence[Tuple[frozenset, frozenset]]) -> Optional[float]:
    """Kappa de Cohen cuando todas las filas tienen exactamente una etiqueta en ambos lados."""
    if not pairs or any(len(ai) != 1 or len(human) != 1 for ai, human in pairs):
        return None
    n = len(pairs)
    observed = sum(1 for ai, human in pairs if ai == human) / n
    ai_counts: Dict[str, int] = {}
    human_counts: Dict[str, int] = {}
    for ai, human in pairs:
        (a,), (h,) = tuple(ai), tuple(human)
        ai_counts[a] = ai_counts.get(a, 0) + 1
        human_counts[h] = human_counts.get(h, 0) + 1
    expected = sum(ai_counts[label] * human_counts.get(label, 0) for label in ai_counts) / (n * n)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def level(agreement: float) -> str:
    return "alto" if agreement >= 0.90 else "medio" if agreement >= 0.75 else "bajo"


def compute_quality(pairs: Iterable[Tuple[Sequence[str], Sequence[str]]]) -> Dict:
    """pairs: (etiquetas de la IA, etiquetas finales de la persona) por cada fila revisada."""
    rows = [(label_set(ai), label_set(human)) for ai, human in pairs]
    n = len(rows)
    if n == 0:
        return {"reviewed": 0, "agreement": None, "interval": None, "level": None, "reliable": False,
                "kappa": None, "micro_f1": None, "categories": [], "weakest": [], "min_sample": MIN_RELIABLE_SAMPLE}
    exact = sum(1 for ai, human in rows if ai == human)
    low, high = wilson_interval(exact, n)

    categories = sorted({label for ai, human in rows for label in (ai | human)})
    stats = []
    total_tp = total_fp = total_fn = 0
    for category in categories:
        tp = sum(1 for ai, human in rows if category in ai and category in human)
        fp = sum(1 for ai, human in rows if category in ai and category not in human)
        fn = sum(1 for ai, human in rows if category not in ai and category in human)
        total_tp, total_fp, total_fn = total_tp + tp, total_fp + fp, total_fn + fn
        precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
        stats.append({"category": category, "support": tp + fn, "predicted": tp + fp,
                      "precision": precision, "recall": recall, "f1": _f1(tp, fp, fn)})
    agreement = exact / n
    weakest = [
        item for item in sorted((s for s in stats if s["support"] >= 3 and s["f1"] is not None), key=lambda s: s["f1"])
        if item["f1"] < 0.8
    ][:3]
    return {
        "reviewed": n, "agreement": agreement, "interval": [low, high], "level": level(agreement),
        "reliable": n >= MIN_RELIABLE_SAMPLE, "kappa": cohen_kappa(rows), "micro_f1": _f1(total_tp, total_fp, total_fn),
        "categories": sorted(stats, key=lambda s: (s["f1"] is None, s["f1"] if s["f1"] is not None else 0, s["category"])),
        "weakest": weakest, "min_sample": MIN_RELIABLE_SAMPLE,
    }


def pick_sample(candidates: Sequence[int], reviewed: Iterable[int], size: int, seed: Optional[int] = None) -> List[int]:
    """Muestra al azar (sin repetir) de filas aún no revisadas."""
    done = set(reviewed)
    pool = [index for index in candidates if index not in done]
    rng = random.Random(seed)
    return sorted(rng.sample(pool, min(max(size, 0), len(pool))))
