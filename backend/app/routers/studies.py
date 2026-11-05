"""Estudios: carga, consulta, borradores de clasificación y exportación.

Movido desde main.py sin cambios de comportamiento.
"""
import json
import logging
import re
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import coding, export
from ..common import _classification_json, _draft_json, _study_json, get_current_user_id
from ..db import get_db
from ..models import Classification, ClassificationDraft, Respondent, Study
from ..ratelimit import limit_by_user
from ..schemas import ClassificationDraftRequest
from ..services import create_study, dataframe_for_study, excel_sheets, get_study

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/uploads/sheets", dependencies=[Depends(limit_by_user("upload-sheets", 30, 600))])
async def upload_sheets(file: UploadFile = File(...)):
    raw = await file.read()
    return {"sheets": excel_sheets(raw, file.filename or "")}


@router.get("/api/studies")
def list_studies(
    db: Session = Depends(get_db), owner_id: str = Depends(get_current_user_id),
):
    studies = db.scalars(
        select(Study).where(Study.owner_id == owner_id).order_by(Study.created_at.desc())
    ).all()
    return [_study_json(study) for study in studies]


@router.post("/api/studies", dependencies=[Depends(limit_by_user("upload-study", 20, 600))])
async def upload_study(
    file: UploadFile = File(...), name: str = Form(""), sheet: str = Form(""),
    db: Session = Depends(get_db), owner_id: str = Depends(get_current_user_id),
):
    raw = await file.read()
    study = create_study(
        db, raw, file.filename or "encuesta.csv", name or None, sheet or None, owner_id
    )
    return _study_json(study)


@router.get("/api/studies/{study_id}")
def get_study_detail(
    study_id: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    classifications = db.scalars(select(Classification).where(Classification.study_id == study_id)).all()
    return {**_study_json(study), "classifications": [_classification_json(item) for item in classifications]}


@router.delete("/api/studies/{study_id}")
def delete_study(
    study_id: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    db.delete(study)
    db.commit()
    return {"deleted": True}


@router.get("/api/studies/{study_id}/overview")
def study_overview(
    study_id: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    frame = dataframe_for_study(db, study)
    return {
        **_study_json(study),
        "suggested_questions": coding.suggest_open_columns(frame),
        "classifications": [_classification_json(item) for item in db.scalars(
            select(Classification).where(Classification.study_id == study_id).order_by(Classification.updated_at.desc())
        ).all()],
        "preview": json.loads(frame.head(8).to_json(orient="records", date_format="iso", force_ascii=False)),
    }


@router.get("/api/studies/{study_id}/drafts")
def list_classification_drafts(
    study_id: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    get_study(db, study_id, owner_id)
    drafts = db.scalars(select(ClassificationDraft).where(ClassificationDraft.study_id == study_id)
                        .order_by(ClassificationDraft.updated_at.desc())).all()
    return [_draft_json(draft) for draft in drafts]


@router.put("/api/studies/{study_id}/drafts")
def save_classification_draft(
    study_id: str, request: ClassificationDraftRequest, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    if request.question not in study.columns:
        raise HTTPException(400, "La pregunta no existe en este estudio.")
    existing = db.scalar(select(ClassificationDraft).where(
        ClassificationDraft.study_id == study_id, ClassificationDraft.question == request.question
    ))
    item = existing or ClassificationDraft(
        id=__import__("uuid").uuid4().hex, study_id=study_id, question=request.question,
        kind=request.kind, codeframe=[], known_brands=[], context="", multi=request.multi,
        provider=request.provider, model=request.model,
    )
    item.kind = request.kind
    item.codeframe = request.codeframe
    item.known_brands = list(dict.fromkeys(name.strip() for name in request.known_brands if name.strip()))
    item.context = request.context
    item.multi = request.multi
    item.provider = request.provider
    item.model = request.model
    item.updated_at = datetime.now(timezone.utc)
    if existing is None:
        db.add(item)
    db.commit()
    db.refresh(item)
    return _draft_json(item)


@router.delete("/api/studies/{study_id}/drafts/{question:path}")
def delete_classification_draft(
    study_id: str, question: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    get_study(db, study_id, owner_id)
    item = db.scalar(select(ClassificationDraft).where(
        ClassificationDraft.study_id == study_id, ClassificationDraft.question == question
    ))
    if item is not None:
        db.delete(item)
        db.commit()
    return {"deleted": True}


@router.get("/api/studies/{study_id}/rows")
def study_rows(
    study_id: str, offset: int = 0, limit: int = 50, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    limit = max(1, min(limit, 300))
    rows = db.scalars(select(Respondent).where(Respondent.study_id == study_id)
                      .order_by(Respondent.row_index).offset(max(offset, 0)).limit(limit)).all()
    return {"rows": [{"row_index": row.row_index, **row.data} for row in rows], "total": study.row_count}


@router.get("/api/studies/{study_id}/values")
def study_column_values(
    study_id: str, column: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    if column not in study.columns:
        raise HTTPException(400, "La columna no existe en este estudio.")
    rows = db.scalars(select(Respondent).where(Respondent.study_id == study_id)
                      .order_by(Respondent.row_index)).all()
    values = list(dict.fromkeys(
        str(row.data.get(column) if row.data.get(column) is not None else "Sin dato") for row in rows
    ))
    return {"values": values[:1000]}


@router.get("/api/studies/{study_id}/export-categorizations")
def export_study_categorizations(
    study_id: str, db: Session = Depends(get_db),
    owner_id: str = Depends(get_current_user_id),
):
    study = get_study(db, study_id, owner_id)
    saved = db.scalars(select(Classification).where(Classification.study_id == study_id)).all()
    by_question = {item.question: item for item in saved}
    ordered = [by_question[column] for column in study.columns if column in by_question]
    if not ordered:
        raise HTTPException(400, "Este estudio aún no tiene categorizaciones guardadas para exportar.")
    if any(len(item.labels or []) != study.row_count for item in ordered):
        raise HTTPException(409, "Una categorización no coincide con la cantidad de filas del estudio; vuelve a clasificar esa pregunta antes de exportar.")
    frame = dataframe_for_study(db, study)
    workbook = export.build_study_categorization_excel(frame, [
        {"question": item.question, "kind": item.kind, "labels": item.labels or [],
         "categories": item.categories or [], "codeframe": item.codeframe or [],
         "config": item.config or {}, "aliases": item.aliases or {}, "brand_mapping": item.brand_mapping or {}}
        for item in ordered
    ])
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", study.name).strip("_")[:60] or "estudio"
    filename = f"{safe_name}_categorizaciones.xlsx"
    return StreamingResponse(
        BytesIO(workbook),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
