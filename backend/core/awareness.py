"""Rutas del Awareness independiente (carga de CSV/XLSX sin crear estudio).

No toca PostgreSQL ni el flujo de categorización: el archivo se procesa en memoria
y se devuelve el Excel de resultados. La autenticación la aplica el middleware global
de main.py a todo lo que cuelga de /api/.
"""

import logging
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from core import awareness_flex
from .ratelimit import limit_by_user
from .common import public_error
from .services import _read_dataframe, excel_sheets, read_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/awareness-flex", tags=["awareness-independiente"])


class ValidateRequest(BaseModel):
    columns: list[str] = Field(default_factory=list, max_length=500)
    config: dict


def _config_or_400(raw):
    try:
        return awareness_flex.parse_config(raw)
    except Exception as exc:
        logger.info("Configuración de Awareness no válida: %s", exc)
        raise HTTPException(400, "Configuración no válida: " + public_error(exc, "revisa el formato de la configuración.")) from exc


async def _load_frame(file: UploadFile, sheet: str):
    """Lee el archivo subido sin bloquear el servidor (pandas/openpyxl son lentos y síncronos)."""
    raw = await read_upload(file)
    return await run_in_threadpool(_read_dataframe, raw, file.filename or "datos.csv", sheet or None)


@router.get("/presets")
def get_presets():
    return awareness_flex.presets()


@router.post("/inspect", dependencies=[Depends(limit_by_user("awareness-inspect", 60, 600))])
async def inspect_file(file: UploadFile = File(...), sheet: str = Form("")):
    raw = await read_upload(file)
    name = file.filename or "datos.csv"
    sheets = await run_in_threadpool(excel_sheets, raw, name)
    frame = await run_in_threadpool(_read_dataframe, raw, name, sheet or None)
    return {"filename": name, "sheets": sheets, "columns": [str(c) for c in frame.columns], "row_count": len(frame)}


@router.post("/validate")
def validate_columns(request: ValidateRequest):
    config = _config_or_400(request.config)
    return {"rows": awareness_flex.detect_columns(request.columns, config)}


@router.post("/suggest", dependencies=[Depends(limit_by_user("awareness-suggest", 40, 600))])
async def suggest_brands(file: UploadFile = File(...), config: str = Form(...), sheet: str = Form("")):
    """Propone la lista de marcas a partir de las respuestas (agrupa las escritas parecido)."""
    cfg = _config_or_400(config)
    frame = await _load_frame(file, sheet)
    try:
        return await run_in_threadpool(awareness_flex.suggest_entities, frame, cfg)
    except Exception as exc:
        logger.exception("Fallo en Awareness independiente")
        raise HTTPException(400, "No se pudo proponer marcas: " + public_error(exc, "revisa la configuración de columnas.")) from exc


@router.post("/preview", dependencies=[Depends(limit_by_user("awareness-preview", 40, 600))])
async def preview_awareness(file: UploadFile = File(...), config: str = Form(...), sheet: str = Form("")):
    cfg = _config_or_400(config)
    frame = await _load_frame(file, sheet)
    try:
        return await run_in_threadpool(awareness_flex.preview_results, frame, cfg)
    except Exception as exc:
        logger.exception("Fallo en Awareness independiente")
        raise HTTPException(400, "No se pudo calcular la vista previa: " + public_error(exc, "revisa la configuración de columnas.")) from exc


@router.post("/report", dependencies=[Depends(limit_by_user("awareness-report", 40, 600))])
async def build_report(file: UploadFile = File(...), config: str = Form(...), sheet: str = Form("")):
    cfg = _config_or_400(config)
    frame = await _load_frame(file, sheet)
    try:
        workbook = await run_in_threadpool(awareness_flex.generate_report, frame, cfg)
    except Exception as exc:
        logger.exception("Fallo en Awareness independiente")
        raise HTTPException(400, "No se pudo generar el reporte: " + public_error(exc, "revisa la configuración de columnas.")) from exc
    return StreamingResponse(
        BytesIO(workbook),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Reporte_Awareness_Estructural.xlsx"', "Content-Encoding": "identity"},
    )
