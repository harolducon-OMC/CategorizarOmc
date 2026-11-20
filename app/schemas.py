from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints

# Proveedor y modelo llegan del cliente: se acotan para que no se usen como vector de abuso o de inyección en logs.
ProviderId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,40}$")]
ModelId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:/@+-]{1,120}$")]
ContextText = Annotated[str, StringConstraints(max_length=4000)]
BrandName = Annotated[str, StringConstraints(max_length=120)]


class ProposeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    context: ContextText = ""
    max_categories: int = Field(default=10, ge=5, le=20)
    provider: ProviderId = "gemini"
    model: ModelId = "gemini-3.5-flash-lite"


class ClassifyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    kind: Literal["themes", "brands", "sentiment"]
    codeframe: list[dict] = Field(default_factory=list, max_length=60)
    known_brands: list[BrandName] = Field(default_factory=list, max_length=500)
    context: ContextText = ""
    multi: bool = True
    max_categories: int = Field(default=10, ge=5, le=20)
    provider: ProviderId = "gemini"
    model: ModelId = "gemini-3.5-flash-lite"


class ClassificationDraftRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    kind: Literal["themes", "brands", "sentiment"]
    codeframe: list[dict] = Field(default_factory=list, max_length=60)
    known_brands: list[BrandName] = Field(default_factory=list, max_length=500)
    context: ContextText = ""
    multi: bool = True
    provider: ProviderId = "gemini"
    model: ModelId = "gemini-3.5-flash-lite"


class LabelEdit(BaseModel):
    row_index: int = Field(ge=0)
    labels: list[str] = Field(min_length=1, max_length=30)


class LabelsBatchEdit(BaseModel):
    changes: list[LabelEdit] = Field(min_length=1, max_length=500)


class AwarenessAnalysisRequest(BaseModel):
    name: str = Field(default="Awareness", max_length=100)
    tom_column: str = Field(default="", max_length=200)
    spontaneous_columns: list[str] = Field(default_factory=list, max_length=50)
    aided_columns: list[str] = Field(default_factory=list, max_length=50)


class AwarenessRequest(BaseModel):
    classification_id: str = Field(max_length=64)
    classification_ids: list[str] = Field(default_factory=list, max_length=20)
    entities: list[str] = Field(default_factory=list, max_length=500)
    analyses: list[AwarenessAnalysisRequest] = Field(default_factory=list, max_length=6)
    # Campos heredados para clientes anteriores a los dos perfiles de análisis.
    tom_column: str = Field(default="", max_length=200)
    spontaneous_columns: list[str] = Field(default_factory=list, max_length=50)
    aided_columns: list[str] = Field(default_factory=list, max_length=50)
    demographics: dict[str, str] = Field(default_factory=dict, max_length=10)
    segment_column: str = Field(default="", max_length=200)
    segment_value: str = Field(default="", max_length=200)


class HelpChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class HelpChatRequest(BaseModel):
    provider: ProviderId = "gemini"
    model: ModelId = "gemini-3.5-flash-lite"
    messages: list[HelpChatMessage] = Field(min_length=1, max_length=12)
