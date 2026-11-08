import io
import json
import pandas as pd
from .policies import provider_allowed
from .cache import MAX_CACHED_CELLS, MISSING, frame_cache
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth_models import User
from .models import Respondent, Study
from core.llm import LLM, PROVIDER_CONFIG

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ROWS = 200_000
MAX_COLUMNS = 500


def _read_dataframe(raw: bytes, filename: str, sheet: str | None = None) -> pd.DataFrame:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El archivo supera el límite de 25 MB.")
    suffix = filename.lower()
    try:
        if suffix.endswith(".csv"):
            frame = None
            for encoding in ("utf-8-sig", "latin-1"):
                try:
                    frame = pd.read_csv(io.BytesIO(raw), sep=None, engine="python", encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if frame is None:
                raise ValueError("No se reconoce la codificación del CSV.")
        elif suffix.endswith(".xlsx"):
            frame = pd.read_excel(io.BytesIO(raw), sheet_name=sheet or 0, engine="openpyxl")
        else:
            raise HTTPException(415, "Formato no compatible. Usa CSV o XLSX.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer el archivo: {exc}") from exc
    if frame.empty:
        raise HTTPException(400, "El archivo no contiene registros.")
    if len(frame) > MAX_ROWS or len(frame.columns) > MAX_COLUMNS:
        raise HTTPException(413, "El archivo supera el máximo de 200.000 filas o 500 columnas.")
    columns = []
    seen = set()
    for raw_name in frame.columns:
        name = str(raw_name).strip() or "Columna"
        base, suffix_n, candidate = name, 2, name
        while candidate in seen:
            candidate = f"{base} ({suffix_n})"
            suffix_n += 1
        columns.append(candidate)
        seen.add(candidate)
    frame.columns = columns
    return frame


def excel_sheets(raw: bytes, filename: str) -> list[str]:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El archivo supera el límite de 25 MB.")
    if not filename.lower().endswith(".xlsx"):
        return []
    try:
        return pd.ExcelFile(io.BytesIO(raw), engine="openpyxl").sheet_names
    except Exception as exc:
        raise HTTPException(400, f"No se pudieron leer las hojas del Excel: {exc}") from exc


def create_study(
    db: Session, raw: bytes, filename: str, name: str | None, sheet: str | None, owner_id: str
) -> Study:
    frame = _read_dataframe(raw, filename, sheet)
    study = Study(
        id=__import__("uuid").uuid4().hex,
        owner_id=owner_id,
        name=(name or filename.rsplit(".", 1)[0]).strip()[:240] or filename,
        source_filename=filename[:255],
        columns=list(frame.columns),
        row_count=len(frame),
    )
    db.add(study)
    clean = frame.astype(object).where(pd.notna(frame), None)
    records = json.loads(clean.to_json(orient="records", date_format="iso", force_ascii=False))
    for start in range(0, len(records), 1000):
        db.add_all([
            Respondent(study_id=study.id, row_index=start + index, data=record)
            for index, record in enumerate(records[start : start + 1000])
        ])
    db.commit()
    db.refresh(study)
    return study


def dataframe_for_study(db: Session, study: Study) -> pd.DataFrame:
    """Datos del estudio como DataFrame. Se cachea en memoria: las respuestas no cambian tras la carga.

    Siempre devuelve una copia, así que los endpoints pueden modificarla sin afectar el caché.
    """
    key = f"{study.id}:{study.row_count}"
    cached = frame_cache.get(key)
    if cached is not MISSING:
        return cached.copy()
    rows = db.scalars(  # solo la columna JSON: evita construir un objeto ORM por fila
        select(Respondent.data).where(Respondent.study_id == study.id).order_by(Respondent.row_index)
    ).all()
    frame = pd.DataFrame(rows, columns=study.columns)
    if frame.size <= MAX_CACHED_CELLS:
        frame_cache.set(key, frame)
    return frame.copy()


def get_study(db: Session, study_id: str, owner_id: str) -> Study:
    study = db.scalar(
        select(Study).where(Study.id == study_id, Study.owner_id == owner_id)
    )
    if study is None:
        raise HTTPException(404, "No se encontró el estudio.")
    return study


def get_user_id(db: Session, email: str) -> str:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise HTTPException(401, "La sesión no corresponde a un usuario activo.")
    return user.id


def create_llm(provider: str, model: str, api_key: str | None) -> LLM:
    if provider not in PROVIDER_CONFIG:
        raise HTTPException(400, "Proveedor de IA no reconocido.")
    if not provider_allowed(provider):
        raise HTTPException(403, "La política de seguridad de tu organización no permite este proveedor de IA. Elige otro en Ajustes.")
    if not api_key:
        raise HTTPException(400, "Escribe una API key en Ajustes para llamar al modelo.")
    try:
        return LLM(api_key, fast=model, smart=model, provider=provider)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
