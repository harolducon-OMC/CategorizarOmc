"""Awareness integrado al flujo de categorización.

Movido desde main.py sin cambios de comportamiento.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import awareness
from ..common import _class_or_404, get_current_user_id
from ..db import get_db
from ..models import Classification
from ..schemas import AwarenessAnalysisRequest, AwarenessRequest
from ..services import dataframe_for_study, get_study

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/studies/{study_id}/awareness")
def calculate_awareness(
    study_id: str, request: AwarenessRequest, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    source_ids = list(dict.fromkeys(request.classification_ids or [request.classification_id]))
    source_items = [_class_or_404(db, class_id, owner_id) for class_id in source_ids]
    if any(item.study_id != study_id or item.kind != "brands" for item in source_items):
        raise HTTPException(400, "Selecciona una clasificación de marcas de este estudio.")
    frame = dataframe_for_study(db, study)
    merged_entities = list(dict.fromkeys(entity for item in source_items for entity in (item.entities or [])))
    merged_aliases = {}
    for source in source_items:
        merged_aliases.update(source.aliases or {})
    entities = request.entities or merged_entities
    if not entities:
        raise HTTPException(400, "No hay marcas para analizar.")

    analysis_requests = request.analyses or [AwarenessAnalysisRequest(
        name="Awareness",
        tom_column=request.tom_column,
        spontaneous_columns=request.spontaneous_columns,
        aided_columns=request.aided_columns,
    )]
    active_analyses = [
        item for item in analysis_requests
        if item.tom_column or item.spontaneous_columns or item.aided_columns
    ]
    if not active_analyses:
        raise HTTPException(400, "Configura al menos una pregunta TOM, espontánea o ayudada en uno de los análisis.")

    invalid_cols = [
        column for item in active_analyses
        for column in [item.tom_column, *item.spontaneous_columns, *item.aided_columns]
        if column and column not in frame.columns
    ]
    invalid_cols.extend(
        column for column in [*request.demographics.values(), request.segment_column]
        if column and column not in frame.columns
    )
    if invalid_cols:
        raise HTTPException(400, f"Columnas desconocidas: {', '.join(invalid_cols)}")
    demo_cols = {key: request.demographics.get(key) or None for key in
                 ("sexo", "edad", "departamento", "estrato", "ingreso")}
    categorized_items = db.scalars(
        select(Classification).where(
            Classification.study_id == study_id,
            Classification.kind == "brands",
        )
    ).all()
    analysis_frame = awareness.frame_with_categorized_responses(frame, categorized_items)
    try:
        selected_value = request.segment_value
        if request.segment_column:
            frame[request.segment_column] = frame[request.segment_column].fillna("Sin dato").astype(str)
            analysis_frame[request.segment_column] = frame[request.segment_column]
        analysis_results = []
        for item in active_analyses:
            config = {
                "name": item.name or "Awareness",
                "tom": item.tom_column or "0",
                "esp": "\n".join(item.spontaneous_columns) or "0",
                "ayu": "\n".join(item.aided_columns) or "0",
            }
            _, indicators, _ = awareness.build_analysis(
                analysis_frame, demo_cols, config, entities, merged_aliases, [], 0
            )
            table = awareness.category_table(
                indicators, analysis_frame, request.segment_column or None,
                selected_value if request.segment_column else None, entities,
            )
            rows = table.to_dict(orient="records")
            analysis_results.append({"name": config["name"], "rows": rows})
    except Exception as exc:
        logger.exception("Fallo en calculate_awareness")
        raise HTTPException(400, f"No se pudo calcular Awareness: {exc}") from exc
    base = len(frame) if not request.segment_column else int(
        (analysis_frame[request.segment_column].fillna("Sin dato").astype(str) == selected_value).sum()
    )
    return {
        "base": base,
        "rows_total": int(len(frame)),
        "segment_column": request.segment_column,
        "segment_value": selected_value,
        "analyses": analysis_results,
        "rows": analysis_results[0]["rows"],
    }
