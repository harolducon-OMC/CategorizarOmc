from datetime import datetime, timezone
import json
from io import BytesIO
from typing import Optional
import os
import re
import uuid
from dotenv import load_dotenv
load_dotenv()  # lee el .env de la raíz también cuando Uvicorn se lanza desde backend/
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import Classification, ClassificationDraft, Respondent, Study
from .auth_models import User, UserApiKey
from .security import (create_access_token, decrypt_api_key, email_is_allowed, encrypt_api_key, hash_password, token_subject, validate_security_config, verify_password)
from .schemas import AwarenessAnalysisRequest, AwarenessRequest, ClassificationDraftRequest, ClassifyRequest, LabelsBatchEdit, ProposeRequest
from .services import create_llm, create_study, dataframe_for_study, excel_sheets, get_study
from pydantic import BaseModel, Field
from sqlalchemy import func
from core import awareness, brands, coding, export, insights
from core.llm import PROVIDER_CONFIG
from .awareness_flex import router as awareness_flex_router

app = FastAPI(title="Plataforma de Insights API", version="1.0.0")
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path
    public = path in {"/api/health", "/api/auth/register", "/api/auth/login"} or path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc")
    if path.startswith("/api/") and request.method != "OPTIONS" and not public:
        auth = request.headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        email = token_subject(token) if scheme.lower() == "bearer" else None
        if not email:
            return JSONResponse({"detail":"Se requiere un token de acceso válido."}, status_code=401)
        request.state.user_email = email
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store" if path.startswith("/api/auth") else "no-cache"
    return response

app.include_router(awareness_flex_router)


CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables():
    validate_security_config()
    Base.metadata.create_all(bind=engine)


def _study_json(study: Study) -> dict:
    return {
        "id": study.id, "name": study.name, "source_filename": study.source_filename,
        "columns": study.columns, "row_count": study.row_count,
        "created_at": study.created_at.isoformat() if study.created_at else None,
    }


def _classification_json(item: Classification) -> dict:
    return {
        "id": item.id, "study_id": item.study_id, "question": item.question,
        "kind": item.kind, "categories": item.categories, "codeframe": item.codeframe,
        "entities": item.entities, "aliases": item.aliases,
        "config": item.config, "has_insights": bool(item.insights),
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _draft_json(item: ClassificationDraft) -> dict:
    return {
        "id": item.id, "study_id": item.study_id, "question": item.question,
        "kind": item.kind, "codeframe": item.codeframe, "known_brands": item.known_brands,
        "context": item.context, "multi": item.multi, "provider": item.provider,
        "model": item.model, "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _class_or_404(db: Session, classification_id: str) -> Classification:
    item = db.get(Classification, classification_id)
    if item is None:
        raise HTTPException(404, "No se encontró la clasificación.")
    return item


def _labels_without_blank_responses(labels, responses):
    """Limpia resultados antiguos: si la respuesta fuente está vacía, la etiqueta también."""
    stored = labels or []
    return [
        [] if coding.is_blank_response(response)
        else list(stored[index] or []) if index < len(stored)
        else []
        for index, response in enumerate(responses)
    ]


class AuthPayload(BaseModel):
    email: str = Field(min_length=6, max_length=320)
    password: str = Field(min_length=12, max_length=256)


class ApiKeyPayload(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)


@app.post("/api/auth/register")
def register(payload: AuthPayload, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+", email):
        raise HTTPException(422, "Ingresa un correo electrónico válido.")
    if not email_is_allowed(email):
        raise HTTPException(403, "El registro solo permite correos del dominio corporativo configurado.")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo.")
    user = User(id=uuid.uuid4().hex, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    return {"access_token": create_access_token(email), "token_type": "bearer", "email": email}


@app.post("/api/auth/login")
def login(payload: AuthPayload, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    return {"access_token": create_access_token(user.email), "token_type": "bearer", "email": user.email}


@app.get("/api/auth/me")
def current_user(request: Request):
    return {"email": request.state.user_email}



def _api_key_for_user(db: Session, email: str, provider: str, supplied: Optional[str]) -> Optional[str]:
    """La clave temporal del header prevalece; si falta, carga la clave cifrada del usuario."""
    if supplied and supplied.strip():
        return supplied.strip()
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    saved = db.get(UserApiKey, {"user_id": user.id, "provider": provider})
    return decrypt_api_key(saved.encrypted_key) if saved else None


@app.get("/api/me/api-keys")
def list_my_api_keys(request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    records = db.scalars(select(UserApiKey).where(UserApiKey.user_id == user.id)).all()
    return {"providers": [record.provider for record in records]}


@app.put("/api/me/api-keys/{provider}")
def save_my_api_key(provider: str, payload: ApiKeyPayload, request: Request, db: Session = Depends(get_db)):
    if provider not in PROVIDER_CONFIG:
        raise HTTPException(400, "Proveedor de IA no reconocido.")
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(422, "La API key es obligatoria y no puede superar 4096 caracteres.")
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    record = db.get(UserApiKey, {"user_id": user.id, "provider": provider})
    if record is None:
        record = UserApiKey(user_id=user.id, provider=provider, encrypted_key=encrypt_api_key(api_key))
        db.add(record)
    else:
        record.encrypted_key = encrypt_api_key(api_key)
        record.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"provider": provider, "configured": True, "updated_at": record.updated_at.isoformat()}


@app.delete("/api/me/api-keys/{provider}")
def delete_my_api_key(provider: str, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == request.state.user_email.lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    record = db.get(UserApiKey, {"user_id": user.id, "provider": provider})
    if record is not None:
        db.delete(record)
        db.commit()
    return {"provider": provider, "configured": False}

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "connected"}


@app.get("/api/config/providers")
def providers():
    return [{"id": key, "name": item["name"], "default_model": item["default_model"], "models": item["models"]}
            for key, item in PROVIDER_CONFIG.items()]


@app.post("/api/uploads/sheets")
async def upload_sheets(file: UploadFile = File(...)):
    raw = await file.read()
    return {"sheets": excel_sheets(raw, file.filename or "")}


@app.get("/api/studies")
def list_studies(db: Session = Depends(get_db)):
    studies = db.scalars(select(Study).order_by(Study.created_at.desc())).all()
    return [_study_json(study) for study in studies]


@app.post("/api/studies")
async def upload_study(
    file: UploadFile = File(...), name: str = Form(""), sheet: str = Form(""),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    study = create_study(db, raw, file.filename or "encuesta.csv", name or None, sheet or None)
    return _study_json(study)


@app.get("/api/studies/{study_id}")
def get_study_detail(study_id: str, db: Session = Depends(get_db)):
    study = get_study(db, study_id)
    classifications = db.scalars(select(Classification).where(Classification.study_id == study_id)).all()
    return {**_study_json(study), "classifications": [_classification_json(item) for item in classifications]}


@app.delete("/api/studies/{study_id}")
def delete_study(study_id: str, db: Session = Depends(get_db)):
    study = get_study(db, study_id)
    db.delete(study)
    db.commit()
    return {"deleted": True}


@app.get("/api/studies/{study_id}/overview")
def study_overview(study_id: str, db: Session = Depends(get_db)):
    study = get_study(db, study_id)
    frame = dataframe_for_study(db, study)
    return {
        **_study_json(study),
        "suggested_questions": coding.suggest_open_columns(frame),
        "classifications": [_classification_json(item) for item in db.scalars(
            select(Classification).where(Classification.study_id == study_id).order_by(Classification.updated_at.desc())
        ).all()],
        "preview": json.loads(frame.head(8).to_json(orient="records", date_format="iso", force_ascii=False)),
    }


@app.get("/api/studies/{study_id}/drafts")
def list_classification_drafts(study_id: str, db: Session = Depends(get_db)):
    get_study(db, study_id)
    drafts = db.scalars(select(ClassificationDraft).where(ClassificationDraft.study_id == study_id)
                        .order_by(ClassificationDraft.updated_at.desc())).all()
    return [_draft_json(draft) for draft in drafts]


@app.put("/api/studies/{study_id}/drafts")
def save_classification_draft(
    study_id: str, request: ClassificationDraftRequest, db: Session = Depends(get_db),
):
    study = get_study(db, study_id)
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


@app.delete("/api/studies/{study_id}/drafts/{question:path}")
def delete_classification_draft(study_id: str, question: str, db: Session = Depends(get_db)):
    get_study(db, study_id)
    item = db.scalar(select(ClassificationDraft).where(
        ClassificationDraft.study_id == study_id, ClassificationDraft.question == question
    ))
    if item is not None:
        db.delete(item)
        db.commit()
    return {"deleted": True}


@app.get("/api/studies/{study_id}/rows")
def study_rows(study_id: str, offset: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    study = get_study(db, study_id)
    limit = max(1, min(limit, 300))
    rows = db.scalars(select(Respondent).where(Respondent.study_id == study_id)
                      .order_by(Respondent.row_index).offset(max(offset, 0)).limit(limit)).all()
    return {"rows": [{"row_index": row.row_index, **row.data} for row in rows], "total": study.row_count}


@app.get("/api/studies/{study_id}/values")
def study_column_values(study_id: str, column: str, db: Session = Depends(get_db)):
    study = get_study(db, study_id)
    if column not in study.columns:
        raise HTTPException(400, "La columna no existe en este estudio.")
    rows = db.scalars(select(Respondent).where(Respondent.study_id == study_id)
                      .order_by(Respondent.row_index)).all()
    values = list(dict.fromkeys(
        str(row.data.get(column) if row.data.get(column) is not None else "Sin dato") for row in rows
    ))
    return {"values": values[:1000]}


@app.post("/api/studies/{study_id}/propose-categories")
def propose_categories(
    study_id: str, request: ProposeRequest, http_request: Request, db: Session = Depends(get_db),
    api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
):
    study = get_study(db, study_id)
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
        raise HTTPException(502, f"No se pudieron proponer categorías: {exc}") from exc
    return {"codeframe": categories}


@app.post("/api/studies/{study_id}/classifications")
def classify_question(
    study_id: str, request: ClassifyRequest, http_request: Request, db: Session = Depends(get_db),
    api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
):
    study = get_study(db, study_id)
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
            raw = brands.extract_mentions(llm, request.question, texts, known_brands=request.known_brands)
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
    db.commit()
    db.refresh(item)
    return {**_classification_json(item), "stats": stats}


@app.get("/api/studies/{study_id}/classifications")
def list_classifications(study_id: str, db: Session = Depends(get_db)):
    get_study(db, study_id)
    items = db.scalars(select(Classification).where(Classification.study_id == study_id)
                       .order_by(Classification.updated_at.desc())).all()
    return [_classification_json(item) for item in items]


@app.get("/api/classifications/{classification_id}/rows")
def classification_rows(classification_id: str, offset: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    item = _class_or_404(db, classification_id)
    study = get_study(db, item.study_id)
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


@app.patch("/api/classifications/{classification_id}/labels")
def edit_labels(classification_id: str, request: LabelsBatchEdit, db: Session = Depends(get_db)):
    item = _class_or_404(db, classification_id)
    study = get_study(db, item.study_id)
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


@app.get("/api/classifications/{classification_id}/frequencies")
def frequencies(classification_id: str, db: Session = Depends(get_db)):
    item = _class_or_404(db, classification_id)
    study = get_study(db, item.study_id)
    frame = dataframe_for_study(db, study)
    labels = _labels_without_blank_responses(item.labels, frame[item.question].tolist())
    table = coding.frequency_table(labels, item.categories)
    return {"base": coding.valid_base(labels), "rows": table.to_dict(orient="records")}


@app.get("/api/classifications/{classification_id}/segments")
def segment_table(classification_id: str, column: str, db: Session = Depends(get_db)):
    item = _class_or_404(db, classification_id)
    study = get_study(db, item.study_id)
    if column not in study.columns:
        raise HTTPException(400, "La columna de segmento no existe.")
    frame = dataframe_for_study(db, study)
    labels = _labels_without_blank_responses(item.labels, frame[item.question].tolist())
    matrix, bases = coding.crosstab_by_segment(labels, frame[column], item.categories)
    return {"column": column, "segments": [
        {"segment": str(segment), "base": bases[segment], **{
            category: float(matrix.loc[category, segment]) for category in matrix.index
        }} for segment in matrix.columns
    ]}


@app.post("/api/classifications/{classification_id}/insights")
def generate_insights(
    classification_id: str, http_request: Request, provider: str = Form("gemini"), model: str = Form("gemini-3.5-flash-lite"),
    db: Session = Depends(get_db), api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
):
    item = _class_or_404(db, classification_id)
    study = get_study(db, item.study_id)
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
        raise HTTPException(502, f"No se pudieron generar insights: {exc}") from exc
    item.insights = result
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return result


@app.get("/api/classifications/{classification_id}/export")
def export_classification(classification_id: str, db: Session = Depends(get_db)):
    item = _class_or_404(db, classification_id)
    study = get_study(db, item.study_id)
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
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/studies/{study_id}/export-categorizations")
def export_study_categorizations(study_id: str, db: Session = Depends(get_db)):
    study = get_study(db, study_id)
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


@app.post("/api/studies/{study_id}/awareness")
def calculate_awareness(study_id: str, request: AwarenessRequest, db: Session = Depends(get_db)):
    study = get_study(db, study_id)
    source_ids = list(dict.fromkeys(request.classification_ids or [request.classification_id]))
    source_items = [_class_or_404(db, class_id) for class_id in source_ids]
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
            analysis_results.append({"name": config["name"], "rows": table.to_dict(orient="records")})
    except Exception as exc:
        raise HTTPException(400, f"No se pudo calcular Awareness: {exc}") from exc
    base = len(frame) if not request.segment_column else int(
        (analysis_frame[request.segment_column].fillna("Sin dato").astype(str) == selected_value).sum()
    )
    return {
        "base": base,
        "segment_column": request.segment_column,
        "segment_value": selected_value,
        "analyses": analysis_results,
        "rows": analysis_results[0]["rows"],
    }