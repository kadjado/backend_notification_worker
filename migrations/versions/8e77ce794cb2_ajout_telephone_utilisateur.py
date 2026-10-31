"""Ajout du téléphone aux utilisateurs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8e77ce794cb2"
down_revision: Union[str, Sequence[str], None] = "b7c4e2196a31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "utilisateurs",
        sa.Column("telephone", sa.String(length=20), nullable=True),
    )
    op.create_unique_constraint(
        "uq_utilisateur_telephone",
        "utilisateurs",
        ["telephone"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_utilisateur_telephone",
        "utilisateurs",
        type_="unique",
    )
    op.drop_column("utilisateurs", "telephone")
