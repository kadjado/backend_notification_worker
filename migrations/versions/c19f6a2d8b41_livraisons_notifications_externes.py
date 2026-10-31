"""Ajoute la file de livraison des notifications externes."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c19f6a2d8b41"
down_revision: Union[str, Sequence[str], None] = "8e77ce794cb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "livraisons_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "notification_id",
            sa.Integer(),
            sa.ForeignKey("notifications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "fiche_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("fiches_paludisme.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("destinataire", sa.String(length=255), nullable=False),
        sa.Column("contenu", sa.JSON(), nullable=False),
        sa.Column(
            "statut",
            sa.String(length=20),
            nullable=False,
            server_default="en_attente",
        ),
        sa.Column(
            "tentatives",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "prochaine_tentative",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("derniere_erreur", sa.Text(), nullable=True),
        sa.Column(
            "cree_le",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("envoye_le", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "canal IN ('whatsapp', 'web_push', 'android_push')",
            name="ck_livraison_notification_canal",
        ),
        sa.CheckConstraint(
            "statut IN ('en_attente', 'en_cours', 'envoyee', 'echec')",
            name="ck_livraison_notification_statut",
        ),
    )
    op.create_index(
        "ix_livraisons_notifications_a_traiter",
        "livraisons_notifications",
        ["statut", "prochaine_tentative"],
    )
    op.create_index(
        "ix_livraisons_notifications_fiche",
        "livraisons_notifications",
        ["fiche_id"],
    )

    op.create_table(
        "appareils_push",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "utilisateur_id",
            sa.Integer(),
            sa.ForeignKey("utilisateurs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jeton", sa.Text(), nullable=False),
        sa.Column("plateforme", sa.String(length=20), nullable=False),
        sa.Column(
            "actif",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "cree_le",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "mis_a_jour_le",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("jeton", name="uq_appareils_push_jeton"),
        sa.CheckConstraint(
            "plateforme IN ('web', 'android')",
            name="ck_appareils_push_plateforme",
        ),
    )
    op.create_index(
        "ix_appareils_push_utilisateur_actif",
        "appareils_push",
        ["utilisateur_id", "actif"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_appareils_push_utilisateur_actif",
        table_name="appareils_push",
    )
    op.drop_table("appareils_push")

    op.drop_index(
        "ix_livraisons_notifications_fiche",
        table_name="livraisons_notifications",
    )
    op.drop_index(
        "ix_livraisons_notifications_a_traiter",
        table_name="livraisons_notifications",
    )
    op.drop_table("livraisons_notifications")
