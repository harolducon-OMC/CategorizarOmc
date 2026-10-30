from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Study(Base):
    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    columns: Mapped[list] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    respondents: Mapped[list["Respondent"]] = relationship(
        back_populates="study", cascade="all, delete-orphan", passive_deletes=True
    )
    classifications: Mapped[list["Classification"]] = relationship(
        back_populates="study", cascade="all, delete-orphan", passive_deletes=True
    )


class Respondent(Base):
    __tablename__ = "respondents"
    __table_args__ = (UniqueConstraint("study_id", "row_index", name="uq_respondent_study_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    study: Mapped[Study] = relationship(back_populates="respondents")


class Classification(Base):
    __tablename__ = "classifications"
    __table_args__ = (UniqueConstraint("study_id", "question", name="uq_classification_study_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    labels: Mapped[list] = mapped_column(JSONB, nullable=False)
    categories: Mapped[list] = mapped_column(JSONB, nullable=False)
    codeframe: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    entities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    aliases: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    brand_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    insights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    study: Mapped[Study] = relationship(back_populates="classifications")


class ClassificationDraft(Base):
    __tablename__ = "classification_drafts"
    __table_args__ = (UniqueConstraint("study_id", "question", name="uq_draft_study_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    codeframe: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    known_brands: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    multi: Mapped[bool] = mapped_column(default=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="gemini")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="gemini-3.5-flash-lite")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )
