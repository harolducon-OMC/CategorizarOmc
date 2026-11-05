"""Índices compuestos para las consultas más frecuentes (listado de estudios y de clasificaciones)."""
from alembic import op

revision = "0002_indices_de_consulta"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_studies_owner_created", "studies", ["owner_id", "created_at"], if_not_exists=True)
    op.create_index("ix_classifications_study_updated", "classifications", ["study_id", "updated_at"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_classifications_study_updated", table_name="classifications", if_exists=True)
    op.drop_index("ix_studies_owner_created", table_name="studies", if_exists=True)
