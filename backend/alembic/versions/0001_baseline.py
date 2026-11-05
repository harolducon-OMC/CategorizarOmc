"""Línea base: esquema actual de la plataforma (users, user_api_keys, studies, respondents, classifications...).

- Base de datos NUEVA: `alembic upgrade head` crea todas las tablas.
- Base de datos EXISTENTE (Neon/Render ya en uso): NO ejecutes upgrade; marca la base con
  `alembic stamp head` para que Alembic sepa que ya está al día.

A partir de aquí, cada cambio de tablas o columnas va en una revisión nueva
(`alembic revision --autogenerate -m "descripcion"`), porque `create_all` nunca
modifica tablas que ya existen.
"""
from alembic import op

from app.db import Base
from app import auth_models, models  # noqa: F401  (registra las tablas)

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("La línea base no se puede revertir: borraría todos los datos.")
