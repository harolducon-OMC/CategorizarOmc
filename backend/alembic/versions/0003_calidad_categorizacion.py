"""Tablas del panel de calidad: línea base de la IA y filas revisadas por una persona.

Las tablas se crean también al arrancar la API (create_all); aquí se usa checkfirst para que
la migración sea segura tanto en bases nuevas como en las que ya las tienen.
"""
from alembic import op

from app.models import ClassificationBaseline, ClassificationReview

revision = "0003_calidad_categorizacion"
down_revision = "0002_indices_de_consulta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    ClassificationBaseline.__table__.create(bind, checkfirst=True)
    ClassificationReview.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    ClassificationReview.__table__.drop(bind, checkfirst=True)
    ClassificationBaseline.__table__.drop(bind, checkfirst=True)
