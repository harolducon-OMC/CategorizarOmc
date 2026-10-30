"""Rutas del Awareness independiente (carga de CSV/XLSX sin crear estudio).

No toca PostgreSQL ni el flujo de categorización: el archivo se procesa en memoria
y se devuelve el Excel de resultados. La autenticación la aplica el middleware global
de main.py a todo lo que cuelga de /api/.
"""

from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import awareness_flex
from .services import _read_dataframe, excel_sheets

router = APIRouter(prefix="/api/awareness-flex", tags=["awareness-independiente"])


class ValidateRequest(BaseModel):
    columns: list[str] = Field(default_factory=list)
    config: dict


def _config_or_400(raw):
    try:
        return awareness_flex.parse_config(raw)
    except Exception as exc:
        raise HTTPException(400, f"Configuración no válida: {exc}") from exc


@router.get("/presets")
def get_presets():
    return awareness_flex.presets()


@router.post("/inspect")
async def inspect_file(file: UploadFile = File(...), sheet: str = Form("")):
    raw = await file.read()
    name = file.filename or "datos.csv"
    sheets = excel_sheets(raw, name)
    frame = _read_dataframe(raw, name, sheet or None)
    return {"filename": name, "sheets": sheets, "columns": [str(c) for c in frame.columns], "row_count": len(frame)}


@router.post("/validate")
def validate_columns(request: ValidateRequest):
    config = _config_or_400(request.config)
    return {"rows": awareness_flex.detect_columns(request.columns, config)}


@router.post("/report")
async def build_report(file: UploadFile = File(...), config: str = Form(...), sheet: str = Form("")):
    cfg = _config_or_400(config)
    raw = await file.read()
    frame = _read_dataframe(raw, file.filename or "datos.csv", sheet or None)
    try:
        workbook = awareness_flex.generate_report(frame, cfg)
    except Exception as exc:
        raise HTTPException(400, f"No se pudo generar el reporte: {exc}") from exc
    return StreamingResponse(
        BytesIO(workbook),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Reporte_Awareness_Estructural.xlsx"'},
    )
