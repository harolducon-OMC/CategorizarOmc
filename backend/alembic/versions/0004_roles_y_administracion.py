"""Roles y administración de cuentas: columnas nuevas de «users», políticas de seguridad y auditoría.

Es idempotente: la API también aplica estos cambios al arrancar (create_all + ensure_schema).
"""
from alembic import op

from app import accounts
from app.auth_models import AdminAuditLog, SecurityPolicy

revision = "0004_roles_y_administracion"
down_revision = "0003_calidad_categorizacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SecurityPolicy.__table__.create(bind, checkfirst=True)
    AdminAuditLog.__table__.create(bind, checkfirst=True)
    accounts.ensure_schema(bind)


def downgrade() -> None:
    raise RuntimeError("No se revierte: eliminaría roles, bloqueos y el historial de auditoría.")
