"""Consolidation des rôles de supervision.

Revision ID: c4f9a2d71b60
Revises: e67148a66f54
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4f9a2d71b60"
down_revision: Union[str, Sequence[str], None] = "e67148a66f54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Retirer l'ancienne contrainte avant de convertir les rôles.
    op.drop_constraint(
        "ck_utilisateur_role",
        "utilisateurs",
        type_="check",
    )

    op.execute("""
        UPDATE utilisateurs
        SET role = 'superviseur'
        WHERE role IN (
            'superviseur_communal',
            'superviseur_prefectoral',
            'superviseur_regional'
        )
    """)

    # N'autoriser que les trois rôles retenus.
    op.create_check_constraint(
        "ck_utilisateur_role",
        "utilisateurs",
        "role IN ('agent_fs', 'superviseur', "
        "'administrateur_national')",
    )


def downgrade() -> None:
    # Retirer la nouvelle contrainte avant de restaurer les anciens rôles.
    op.drop_constraint(
        "ck_utilisateur_role",
        "utilisateurs",
        type_="check",
    )

    # Un retour arrière est refusé si un superviseur n'a aucun périmètre.
    # En cas de plusieurs niveaux, le niveau le plus précis prévaut.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM utilisateurs
                WHERE role = 'superviseur'
                  AND commune_id IS NULL
                  AND prefecture_id IS NULL
                  AND region_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Retour arrière impossible : un superviseur '
                    'ne possède aucun périmètre géographique.';
            END IF;

            UPDATE utilisateurs
            SET role = CASE
                WHEN commune_id IS NOT NULL
                    THEN 'superviseur_communal'
                WHEN prefecture_id IS NOT NULL
                    THEN 'superviseur_prefectoral'
                WHEN region_id IS NOT NULL
                    THEN 'superviseur_regional'
            END
            WHERE role = 'superviseur';
        END
        $$;
    """)

    # Restaurer la contrainte des cinq rôles historiques.
    op.create_check_constraint(
        "ck_utilisateur_role",
        "utilisateurs",
        "role IN ('agent_fs', 'superviseur_communal', "
        "'superviseur_prefectoral', 'superviseur_regional', "
        "'administrateur_national')",
    )
