"""Ajoute l'affectation unique des superviseurs par FS et son audit.

Revision ID: b7c4e2196a31
Revises: 9a72c41d5e30
Create Date: 2026-10-24
"""
from alembic import context, op
import sqlalchemy as sa


revision = "b7c4e2196a31"
down_revision = "9a72c41d5e30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # En mode hors ligne, les resultats des requetes SELECT ne sont
    # pas disponibles. L'index unique verifiera les doublons lors
    # de l'application reelle de la migration.
    if not context.is_offline_mode():
        bind = op.get_bind()
        doublons = bind.execute(
            sa.text(
                """
                SELECT formation_sanitaire_id, COUNT(*)
                FROM utilisateurs
                WHERE role = 'superviseur'
                  AND actif IS TRUE
                  AND formation_sanitaire_id IS NOT NULL
                GROUP BY formation_sanitaire_id
                HAVING COUNT(*) > 1
                """
            )
        ).all()

        if doublons:
            raise RuntimeError(
                "Migration interrompue : plusieurs superviseurs actifs sont "
                "deja affectes a une meme formation sanitaire. "
                "Resoudre ces conflits avant de relancer la migration."
            )

    op.create_index(
        "uq_utilisateur_superviseur_fs_actif",
        "utilisateurs",
        ["formation_sanitaire_id"],
        unique=True,
        postgresql_where=sa.text(
            "role = 'superviseur' AND actif IS TRUE"
        ),
    )

    op.create_table(
        "historique_affectations_superviseurs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "formation_sanitaire_id",
            sa.Integer(),
            sa.ForeignKey("formations_sanitaires.id"),
            nullable=False,
        ),
        sa.Column(
            "ancien_superviseur_id",
            sa.Integer(),
            sa.ForeignKey("utilisateurs.id"),
            nullable=True,
        ),
        sa.Column(
            "nouveau_superviseur_id",
            sa.Integer(),
            sa.ForeignKey("utilisateurs.id"),
            nullable=True,
        ),
        sa.Column(
            "administrateur_id",
            sa.Integer(),
            sa.ForeignKey("utilisateurs.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column(
            "date_operation",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_historique_affectations_superviseurs_formation_sanitaire_id",
        "historique_affectations_superviseurs",
        ["formation_sanitaire_id"],
    )
    op.create_index(
        "ix_historique_affectations_superviseurs_administrateur_id",
        "historique_affectations_superviseurs",
        ["administrateur_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historique_affectations_superviseurs_administrateur_id",
        table_name="historique_affectations_superviseurs",
    )
    op.drop_index(
        "ix_historique_affectations_superviseurs_formation_sanitaire_id",
        table_name="historique_affectations_superviseurs",
    )
    op.drop_table("historique_affectations_superviseurs")
    op.drop_index(
        "uq_utilisateur_superviseur_fs_actif",
        table_name="utilisateurs",
    )
