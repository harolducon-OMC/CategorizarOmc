"""Clasificaciones: proponer categorías, clasificar, editar etiquetas, frecuencias, insights y exportación.

Movido desde main.py sin cambios de comportamiento.
"""
import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, defer

from core import brands, coding, export, insights, quality
from ..cache import result_cache
from ..common import (_api_key_for_user, _class_or_404, _classification_json,
                      _labels_without_blank_responses, get_current_user_id)
from ..db import get_db
from ..models import Classification, ClassificationBaseline, ClassificationDraft, ClassificationReview, Respondent
from ..ratelimit import limit_by_user
from ..schemas import ClassifyRequest, LabelsBatchEdit, ProposeRequest
from ..services import create_llm, dataframe_for_study, get_study

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/studies/{study_id}/propose-categories", dependencies=[Depends(limit_by_user("propose-categories", 15, 600))])
def propose_categories(
    study_id: str, request: ProposeRequest, http_request: Request, db: Session = Depends(get_db),
    api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    if request.question not in study.columns:
        raise HTTPException(400, "La pregunta no existe en este estudio.")
    api_key = _api_key_for_user(db, http_request.state.user_email, request.provider, api_key)
    llm = create_llm(request.provider, request.model, api_key)
    frame = dataframe_for_study(db, study)
    try:
        categories = coding.discover_categories(
            llm, request.question, frame[request.question].fillna("").astype(str).tolist(),
            max_categories=request.max_categories, context=request.context,
        )
    except Exception as exc:
        logger.exception("Fallo en propose_categories")
        raise HTTPException(502, f"No se pudieron proponer categorías: {exc}") from exc
    return {"codeframe": categories}


@router.post("/api/studies/{study_id}/classifications", dependencies=[Depends(limit_by_user("classify", 10, 600))])
def classify_question(
    study_id: str, request: ClassifyRequest, http_request: Request, db: Session = Depends(get_db),
    api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    if request.question not in study.columns:
        raise HTTPException(400, "La pregunta no existe en este estudio.")
    api_key = _api_key_for_user(db, http_request.state.user_email, request.provider, api_key)
    llm = create_llm(request.provider, request.model, api_key)
    frame = dataframe_for_study(db, study)
    texts = frame[request.question].fillna("").astype(str).tolist()
    try:
        if request.kind in ("themes", "sentiment"):
            codeframe = (
                [dict(item) for item in coding.SENTIMENT_CODEFRAME]
                if request.kind == "sentiment"
                else [
                    {"nombre": str(item.get("nombre", "")).strip(),
                     "descripcion": str(item.get("descripcion", "")).strip()}
                    for item in request.codeframe if str(item.get("nombre", "")).strip()
                ]
            )
            if request.kind == "themes" and not codeframe:
                codeframe = coding.discover_categories(
                    llm, request.question, texts, max_categories=request.max_categories, context=request.context
                )
            if not codeframe:
                raise HTTPException(400, "No hay categorías válidas para clasificar.")
            labels, stats = coding.classify(
                llm, request.question, texts, codeframe, multi=request.multi, context=request.context
            )
            categories = coding.categories_in_use(labels, [item["nombre"] for item in codeframe])
            entities, aliases, brand_mapping = [], {}, {}
        else:
            raw = brands.extract_mentions(
                llm, request.question, texts, known_brands=request.known_brands, first_only=not request.multi,
            )
            mapping_table = brands.build_mapping(raw, threshold=88)
            brand_mapping = dict(zip(mapping_table.get("Mención", []), mapping_table.get("Marca normalizada", [])))
            labels = brands.apply_mapping(raw, brand_mapping)
            entities, aliases = brands.entities_and_aliases(raw, brand_mapping)
            categories = list(entities)
            if any(brands.NINGUNA_LABEL in label for label in labels):
                categories.append(brands.NINGUNA_LABEL)
            if any(brands.OTHER_BRAND_LABEL in label for label in labels):
                categories.append(brands.OTHER_BRAND_LABEL)
            codeframe = []
            stats = {"unique_texts": len(set(texts)), "unclassified": 0, "errors": []}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Fallo en classify_question")
        raise HTTPException(502, f"Falló la clasificación: {exc}") from exc

    item = db.scalar(select(Classification).where(
        Classification.study_id == study_id, Classification.question == request.question
    ))
    if item is None:
        item = Classification(
            id=__import__("uuid").uuid4().hex, study_id=study_id,
            question=request.question, kind=request.kind, labels=labels, categories=categories,
        )
        db.add(item)
    item.kind = request.kind
    item.labels = labels
    item.categories = categories
    item.codeframe = codeframe
    item.entities = entities
    item.aliases = aliases
    item.brand_mapping = brand_mapping
    item.config = {
        "context": request.context, "multi": request.multi, "known_brands": request.known_brands,
        "provider": request.provider, "model": request.model,
    }
    item.insights = None
    item.updated_at = datetime.now(timezone.utc)
    draft = db.scalar(select(ClassificationDraft).where(
        ClassificationDraft.study_id == study_id, ClassificationDraft.question == request.question
    ))
    if draft is not None:
        db.delete(draft)
    _save_quality_baseline(db, item, labels)
    db.commit()
    db.refresh(item)
    return {**_classification_json(item), "stats": stats}


@router.get("/api/studies/{study_id}/classifications")
def list_classifications(
    study_id: str, limit: int = 200, offset: int = 0, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    get_study(db, study_id, owner_id)
    items = db.scalars(select(Classification).where(Classification.study_id == study_id)
                       .options(defer(Classification.labels), defer(Classification.brand_mapping))
                       .order_by(Classification.updated_at.desc())
                       .limit(max(1, min(limit, 500))).offset(max(offset, 0))).all()
    return [_classification_json(item) for item in items]


@router.get("/api/classifications/{classification_id}/rows")
def classification_rows(
    classification_id: str, offset: int = 0, limit: int = 100,
    db: Session = Depends(get_db), owner_id: str = Depends(get_current_user_id),
):
    item = _class_or_404(db, classification_id, owner_id)
    study = get_study(db, item.study_id, owner_id)
    limit = max(1, min(limit, 300))
    rows = db.scalars(select(Respondent).where(Respondent.study_id == study.id)
                      .order_by(Respondent.row_index).offset(max(offset, 0)).limit(limit)).all()
    result_rows = []
    stored = item.labels or []
    for row in rows:
        response = row.data.get(item.question)
        labels = [] if coding.is_blank_response(response) else (stored[row.row_index] if row.row_index < len(stored) else [])
        result_rows.append({"row_index": row.row_index, "response": response, "labels": labels})
    return {"rows": result_rows, "total": study.row_count, "categories": item.categories}


@router.patch("/api/classifications/{classification_id}/labels")
def edit_labels(
    classification_id: str, request: LabelsBatchEdit, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    item = _class_or_404(db, classification_id, owner_id)
    study = get_study(db, item.study_id, owner_id)
    allowed = set(item.categories)
    if item.kind == "brands":
        allowed.update([brands.NINGUNA_LABEL, brands.OTHER_BRAND_LABEL, coding.NSNR_LABEL])
    if item.kind in ("themes", "sentiment"):
        allowed.update([coding.OTHER, coding.NSNR_LABEL])
    requested_indexes = [change.row_index for change in request.changes]
    source_rows = db.scalars(select(Respondent).where(
        Respondent.study_id == study.id, Respondent.row_index.in_(requested_indexes)
    )).all() if requested_indexes else []
    blank_indexes = {row.row_index for row in source_rows if coding.is_blank_response(row.data.get(item.question))}
    labels_by_row = [list(row or []) for row in (item.labels or [])]
    skipped_blank = 0
    for change in request.changes:
        if change.row_index < 0 or change.row_index >= len(labels_by_row):
            raise HTTPException(400, f"La fila {change.row_index} no existe.")
        if change.row_index in blank_indexes:
            labels_by_row[change.row_index] = []
            skipped_blank += 1
            continue
        invalid = set(change.labels) - allowed
        if invalid:
            raise HTTPException(400, f"Categorías no válidas: {', '.join(sorted(invalid))}")
        labels = list(dict.fromkeys(change.labels))
        exclusive = next((label for label in labels if label in (coding.NSNR_LABEL, brands.NINGUNA_LABEL)), None)
        labels_by_row[change.row_index] = [exclusive] if exclusive else labels
    item.labels = labels_by_row
    item.insights = None
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"saved": len(request.changes) - skipped_blank, "skipped_blank": skipped_blank, "updated_at": item.updated_at.isoformat()}


def _save_quality_baseline(db: Session, item: Classification, labels) -> None:
    """Guarda lo que decidió la IA para poder medir luego cuánto corrigió la persona.

    Al reclasificar, la línea base se reemplaza y se descartan las revisiones anteriores.
    Si falla (p. ej. tablas sin crear) la clasificación continúa sin panel de calidad.
    """
    try:
        with db.begin_nested():
            db.flush()
            snapshot = [list(row or []) for row in labels]
            baseline = db.get(ClassificationBaseline, item.id)
            if baseline is None:
                db.add(ClassificationBaseline(classification_id=item.id, labels=snapshot))
            else:
                baseline.labels = snapshot
                baseline.created_at = datetime.now(timezone.utc)
            db.execute(delete(ClassificationReview).where(ClassificationReview.classification_id == item.id))
    except Exception:
        logger.warning("No se pudo guardar la línea base de calidad", exc_info=True)


def _allowed_labels(item: Classification) -> set:
    allowed = set(item.categories)
    if item.kind == "brands":
        allowed.update([brands.NINGUNA_LABEL, brands.OTHER_BRAND_LABEL, coding.NSNR_LABEL])
    if item.kind in ("themes", "sentiment"):
        allowed.update([coding.OTHER, coding.NSNR_LABEL])
    return allowed


class QualityReviewItem(BaseModel):
    row_index: int = Field(ge=0)
    labels: list[str] = Field(default_factory=list, max_length=30)


class QualityReviewRequest(BaseModel):
    reviews: list[QualityReviewItem] = Field(min_length=1, max_length=200)


def _quality_payload(db: Session, item: Classification) -> dict:
    reviews = db.scalars(select(ClassificationReview).where(ClassificationReview.classification_id == item.id)).all()
    metrics = quality.compute_quality([(review.ai_labels, review.human_labels) for review in reviews])
    metrics["baseline_available"] = db.get(ClassificationBaseline, item.id) is not None
    return metrics


@router.get("/api/classifications/{classification_id}/quality")
def classification_quality(
    classification_id: str, db: Session = Depends(get_db), owner_id: str = Depends(get_current_user_id),
):
    """Acuerdo entre la IA y la revisión humana, en total y por categoría."""
    item = _class_or_404(db, classification_id, owner_id)
    return _quality_payload(db, item)


@router.get(
    "/api/classifications/{classification_id}/quality/sample",
    dependencies=[Depends(limit_by_user("quality", 60, 600))],
)
def classification_quality_sample(
    classification_id: str, n: int = 30, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    """Muestra al azar de respuestas aún no revisadas para confirmar o corregir su etiqueta."""
    item = _class_or_404(db, classification_id, owner_id)
    get_study(db, item.study_id, owner_id)
    labels = item.labels or []
    texts = db.execute(
        select(Respondent.row_index, Respondent.data[item.question].as_string())
        .where(Respondent.study_id == item.study_id).order_by(Respondent.row_index)
    ).all()
    text_by_row = {row_index: text for row_index, text in texts}
    candidates = [
        index for index, text in text_by_row.items()
        if index < len(labels) and not coding.is_blank_response(text)
    ]
    reviewed = db.scalars(select(ClassificationReview.row_index).where(ClassificationReview.classification_id == item.id)).all()
    chosen = quality.pick_sample(candidates, reviewed, max(1, min(n, 100)))
    baseline = db.get(ClassificationBaseline, item.id)
    ai_source = baseline.labels if baseline is not None else labels
    extras = sorted(_allowed_labels(item) - set(item.categories))
    return {
        "rows": [
            {"row_index": index, "response": str(text_by_row[index])[:1200],
             "ai_labels": list(ai_source[index] if index < len(ai_source) else labels[index] or []),
             "labels": list(labels[index] or [])}
            for index in chosen
        ],
        "categories": [*item.categories, *extras],
        "baseline_available": baseline is not None,
        "pending": max(0, len(set(candidates) - set(reviewed)) - len(chosen)),
    }


@router.put(
    "/api/classifications/{classification_id}/quality/reviews",
    dependencies=[Depends(limit_by_user("quality", 60, 600))],
)
def save_quality_reviews(
    classification_id: str, request: QualityReviewRequest, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    """Guarda las etiquetas finales de la muestra, las aplica a la clasificación y recalcula la calidad."""
    item = _class_or_404(db, classification_id, owner_id)
    allowed = _allowed_labels(item)
    labels_by_row = [list(row or []) for row in (item.labels or [])]
    baseline = db.get(ClassificationBaseline, item.id)
    saved_rows = {
        review.row_index: review for review in db.scalars(select(ClassificationReview).where(
            ClassificationReview.classification_id == item.id,
            ClassificationReview.row_index.in_([change.row_index for change in request.reviews]),
        )).all()
    }
    for change in request.reviews:
        if change.row_index >= len(labels_by_row):
            raise HTTPException(400, f"La fila {change.row_index} no existe.")
        invalid = set(change.labels) - allowed
        if invalid:
            raise HTTPException(400, f"Categorías no válidas: {', '.join(sorted(invalid))}")
        human = list(dict.fromkeys(change.labels))
        exclusive = next((label for label in human if label in (coding.NSNR_LABEL, brands.NINGUNA_LABEL)), None)
        human = [exclusive] if exclusive else human
        ai = list(baseline.labels[change.row_index]) if baseline is not None and change.row_index < len(baseline.labels) \
            else list(labels_by_row[change.row_index])
        review = saved_rows.get(change.row_index)
        if review is None:
            db.add(ClassificationReview(
                id=__import__("uuid").uuid4().hex, classification_id=item.id, row_index=change.row_index,
                ai_labels=ai, human_labels=human,
            ))
        else:
            review.human_labels = human
            review.reviewed_at = datetime.now(timezone.utc)
        labels_by_row[change.row_index] = human
    item.labels = labels_by_row
    item.insights = None
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"saved": len(request.reviews), **_quality_payload(db, item)}


@router.get("/api/classifications/{classification_id}/frequencies")
def frequencies(
    classification_id: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    item = _class_or_404(db, classification_id, owner_id)
    study = get_study(db, item.study_id, owner_id)
    stamp = item.updated_at.isoformat() if item.updated_at else "0"
    def build():
        frame = dataframe_for_study(db, study)
        labels = _labels_without_blank_responses(item.labels, frame[item.question].tolist())
        table = coding.frequency_table(labels, item.categories)
        return {"base": coding.valid_base(labels), "rows": table.to_dict(orient="records")}

    return result_cache.get_or_build(f"freq:{item.id}:{stamp}", 600, build)


@router.get("/api/classifications/{classification_id}/segments")
def segment_table(
    classification_id: str, column: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    item = _class_or_404(db, classification_id, owner_id)
    study = get_study(db, item.study_id, owner_id)
    if column not in study.columns:
        raise HTTPException(400, "La columna de segmento no existe.")
    stamp = item.updated_at.isoformat() if item.updated_at else "0"
    def build():
        frame = dataframe_for_study(db, study)
        labels = _labels_without_blank_responses(item.labels, frame[item.question].tolist())
        matrix, bases = coding.crosstab_by_segment(labels, frame[column], item.categories)
        return {"column": column, "segments": [
            {"segment": str(segment), "base": bases[segment], **{
                category: float(matrix.loc[category, segment]) for category in matrix.index
            }} for segment in matrix.columns
        ]}

    return result_cache.get_or_build(f"seg:{item.id}:{stamp}:{column}", 600, build)


@router.post("/api/classifications/{classification_id}/insights", dependencies=[Depends(limit_by_user("insights", 10, 600))])
def generate_insights(
    classification_id: str, http_request: Request, provider: str = Form("gemini"), model: str = Form("gemini-3.5-flash-lite"),
    db: Session = Depends(get_db), api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    owner_id: str = Depends(get_current_user_id),
):
    item = _class_or_404(db, classification_id, owner_id)
    study = get_study(db, item.study_id, owner_id)
    api_key = _api_key_for_user(db, http_request.state.user_email, provider, api_key)
    llm = create_llm(provider, model, api_key)
    frame = dataframe_for_study(db, study)
    labels = _labels_without_blank_responses(item.labels, frame[item.question].tolist())
    try:
        result = insights.build_insights(
            llm, item.question, frame[item.question].fillna("").astype(str).tolist(), labels,
            item.categories, context=item.config.get("context", ""),
        )
    except Exception as exc:
        logger.exception("Fallo en generate_insights")
        raise HTTPException(502, f"No se pudieron generar insights: {exc}") from exc
    item.insights = result
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return result


@router.get("/api/classifications/{classification_id}/export")
def export_classification(
    classification_id: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    item = _class_or_404(db, classification_id, owner_id)
    study = get_study(db, item.study_id, owner_id)
    frame = dataframe_for_study(db, study)
    labels = _labels_without_blank_responses(item.labels, frame[item.question].tolist())
    report = export.build_study_categorization_excel(frame, [{
        "question": item.question, "kind": item.kind, "labels": labels,
        "categories": item.categories or [], "codeframe": item.codeframe or [],
        "config": item.config or {}, "aliases": item.aliases or {},
        "brand_mapping": item.brand_mapping or {},
    }])
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", study.name).strip("_")[:60] or "estudio"
    filename = f"{safe_name}_categorizacion.xlsx"
    return StreamingResponse(
        BytesIO(report), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Encoding": "identity"},
    )
