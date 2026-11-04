"""Ajout des jetons de renouvellement."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# CONSERVE ici le revision généré automatiquement par Alembic.
revision: str = "e5d5b3bc0fd8"
down_revision: Union[str, Sequence[str], None] = "c19f6a2d8b41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "utilisateur_id",
            sa.Integer(),
            sa.ForeignKey("utilisateurs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "cree_le",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoque_le",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "remplace_par_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_refresh_tokens_token_hash",
        ),
    )

    op.create_index(
        "ix_refresh_tokens_utilisateur_expiration",
        "refresh_tokens",
        ["utilisateur_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_refresh_tokens_utilisateur_expiration",
        table_name="refresh_tokens",
    )
    op.drop_table("refresh_tokens")