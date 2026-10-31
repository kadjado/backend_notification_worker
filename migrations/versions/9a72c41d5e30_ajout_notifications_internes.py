"""Ajout des notifications internes.

Revision ID: 9a72c41d5e30
Revises: c4f9a2d71b60
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa


revision = "9a72c41d5e30"
down_revision = "c4f9a2d71b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("titre", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fiche_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "cree_le",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "lue_le",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["utilisateur_id"],
            ["utilisateurs.id"],
            name="fk_notifications_utilisateur_id_utilisateurs",
        ),
        sa.ForeignKeyConstraint(
            ["fiche_id"],
            ["fiches_paludisme.id"],
            name="fk_notifications_fiche_id_fiches_paludisme",
        ),
    )
    op.create_index(
        "ix_notifications_utilisateur_lue_cree",
        "notifications",
        ["utilisateur_id", "lue_le", "cree_le"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_fiche_id",
        "notifications",
        ["fiche_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_fiche_id", table_name="notifications")
    op.drop_index(
        "ix_notifications_utilisateur_lue_cree",
        table_name="notifications",
    )
    op.drop_table("notifications")
