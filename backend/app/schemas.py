from typing import Literal
from pydantic import BaseModel, Field


class ProposeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    context: str = ""
    max_categories: int = Field(default=10, ge=5, le=20)
    provider: str = "gemini"
    model: str = "gemini-3.5-flash-lite"


class ClassifyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    kind: Literal["themes", "brands", "sentiment"]
    codeframe: list[dict] = Field(default_factory=list)
    known_brands: list[str] = Field(default_factory=list)
    context: str = ""
    multi: bool = True
    max_categories: int = Field(default=10, ge=5, le=20)
    provider: str = "gemini"
    model: str = "gemini-3.5-flash-lite"


class ClassificationDraftRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    kind: Literal["themes", "brands", "sentiment"]
    codeframe: list[dict] = Field(default_factory=list)
    known_brands: list[str] = Field(default_factory=list)
    context: str = ""
    multi: bool = True
    provider: str = "gemini"
    model: str = "gemini-3.5-flash-lite"


class LabelEdit(BaseModel):
    row_index: int = Field(ge=0)
    labels: list[str] = Field(min_length=1)


class LabelsBatchEdit(BaseModel):
    changes: list[LabelEdit] = Field(min_length=1, max_length=500)


class AwarenessRequest(BaseModel):
    classification_id: str
    classification_ids: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    tom_column: str = ""
    spontaneous_columns: list[str] = Field(default_factory=list)
    aided_columns: list[str] = Field(default_factory=list)
    demographics: dict[str, str] = Field(default_factory=dict)
    segment_column: str = ""
    segment_value: str = ""
