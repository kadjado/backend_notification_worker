
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Index, Integer, JSON, String, Text, UniqueConstraint, text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid
from datetime import timedelta

class Base(DeclarativeBase):
    pass


def now_utc():
    return datetime.now(timezone.utc)


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)


class Prefecture(Base):
    __tablename__ = "prefectures"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id"), nullable=False, index=True
    )


class Commune(Base):
    __tablename__ = "communes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    prefecture_id: Mapped[int] = mapped_column(
        ForeignKey("prefectures.id"), nullable=False, index=True
    )


class FormationSanitaire(Base):
    __tablename__ = "formations_sanitaires"
    __table_args__ = (
        CheckConstraint(
            "type_fs IN ('USP', 'CMS', 'HÃ´pital')",
            name="ck_fs_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    libelle: Mapped[str] = mapped_column(String(200), nullable=False)
    type_fs: Mapped[str] = mapped_column(String(20), nullable=False)
    commune_id: Mapped[int] = mapped_column(
        ForeignKey("communes.id"), nullable=False, index=True
    )
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TypeTDR(Base):
    __tablename__ = "types_tdr"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    libelle: Mapped[str] = mapped_column(String(150), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    __table_args__ = (
        CheckConstraint(
            "role IN ('agent_fs', 'superviseur', "
            "'administrateur_national')",
            name="ck_utilisateur_role",
        ),
        Index(
            "uq_utilisateur_superviseur_fs_actif",
            "formation_sanitaire_id",
            unique=True,
            postgresql_where=text("role = 'superviseur' AND actif IS TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    prenom: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    telephone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    fonction: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)

    formation_sanitaire_id: Mapped[int | None] = mapped_column(
        ForeignKey("formations_sanitaires.id"), nullable=True
    )
    commune_id: Mapped[int | None] = mapped_column(
        ForeignKey("communes.id"), nullable=True
    )
    prefecture_id: Mapped[int | None] = mapped_column(
        ForeignKey("prefectures.id"), nullable=True
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id"), nullable=True
    )

    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class FichePaludisme(Base):
    __tablename__ = "fiches_paludisme"
    __table_args__ = (
        UniqueConstraint(
            "formation_sanitaire_id",
            "date_consultation",
            "num_oc",
            name="uq_fiche_fs_date_numoc",
        ),
        CheckConstraint("age >= 0 AND age <= 120", name="ck_fiche_age"),
        CheckConstraint("mois >= 1 AND mois <= 12", name="ck_fiche_mois"),
        CheckConstraint("sexe IN ('M', 'F')", name="ck_fiche_sexe"),
        CheckConstraint(
            "type_consultation IN ('Nouveau cas', 'Reconsultation', 'RÃ©fÃ©rÃ©')",
            name="ck_fiche_type_consultation",
        ),
        CheckConstraint(
            "diagnostic IN ('Paludisme simple', 'Paludisme grave', "
            "'Non confirmÃ©', 'Autre')",
            name="ck_fiche_diagnostic",
        ),
        CheckConstraint(
            "issue_hospitalisation IS NULL OR issue_hospitalisation IN "
            "('GuÃ©ri', 'TransfÃ©rÃ©', 'DÃ©cÃ©dÃ©', "
            "'Sorti contre avis', 'En cours')",
            name="ck_fiche_issue",
        ),
        Index("ix_fiche_date", "date_consultation"),
        Index("ix_fiche_fs_date", "formation_sanitaire_id", "date_consultation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    numero_fiche: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False
    )
    formation_sanitaire_id: Mapped[int] = mapped_column(
        ForeignKey("formations_sanitaires.id"), nullable=False, index=True
    )

    # Section B â€” Collecte et patient
    date_consultation: Mapped[date] = mapped_column(Date, nullable=False)
    num_oc: Mapped[str] = mapped_column(String(50), nullable=False)
    mois: Mapped[int] = mapped_column(Integer, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    sexe: Mapped[str] = mapped_column(String(1), nullable=False)
    grossesse: Mapped[str | None] = mapped_column(String(20))
    tpi1: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tpi2: Mapped[str] = mapped_column(String(20), nullable=False)

    # Section C â€” Consultation
    type_consultation: Mapped[str] = mapped_column(String(30), nullable=False)
    fievre: Mapped[bool] = mapped_column(Boolean, nullable=False)
    motif_consultation: Mapped[str | None] = mapped_column(String(255))

    # Section D â€” Examens et diagnostic
    ge_realisee: Mapped[bool] = mapped_column(Boolean, nullable=False)
    type_ge: Mapped[str | None] = mapped_column(String(30))
    charge_sigep: Mapped[str | None] = mapped_column(String(50))
    tdr_realise: Mapped[bool] = mapped_column(Boolean, nullable=False)
    type_tdr_id: Mapped[int | None] = mapped_column(
        ForeignKey("types_tdr.id")
    )
    resultat_tdr: Mapped[str | None] = mapped_column(String(20))
    numero_laboratoire: Mapped[str | None] = mapped_column(String(50))
    diagnostic: Mapped[str] = mapped_column(String(30), nullable=False)

    # Section E â€” Traitement
    asaq: Mapped[bool] = mapped_column(Boolean, nullable=False)
    arlm: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quinine_comprime: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quinine_injectable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    artesunate_injectable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    autre_traitement: Mapped[str | None] = mapped_column(String(255))

    # Section F â€” Hospitalisation
    hospitalise: Mapped[bool] = mapped_column(Boolean, nullable=False)
    date_sortie: Mapped[date | None] = mapped_column(Date)
    issue_hospitalisation: Mapped[str | None] = mapped_column(String(30))

    # Section G â€” Validation et synchronisation
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False
    )
    date_saisie: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    fonction_agent: Mapped[str] = mapped_column(String(150), nullable=False)
    validation_confirmee: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    validee_par_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "utilisateurs.id",
            name="fk_fiches_paludisme_validee_par_id_utilisateurs",
        ),
        nullable=True,
    )
    validee_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version}
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    modifie_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc,
        nullable=False
    )
    supprime_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class HistoriquePermutationAffectation(Base):
    __tablename__ = "historique_permutations_affectations"

    id: Mapped[int] = mapped_column(primary_key=True)

    agent_a_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False, index=True
    )
    agent_b_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False, index=True
    )
    administrateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False, index=True
    )

    ancienne_fs_a_id: Mapped[int] = mapped_column(
        ForeignKey("formations_sanitaires.id"), nullable=False
    )
    nouvelle_fs_a_id: Mapped[int] = mapped_column(
        ForeignKey("formations_sanitaires.id"), nullable=False
    )
    ancienne_fs_b_id: Mapped[int] = mapped_column(
        ForeignKey("formations_sanitaires.id"), nullable=False
    )
    nouvelle_fs_b_id: Mapped[int] = mapped_column(
        ForeignKey("formations_sanitaires.id"), nullable=False
    )

    date_operation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class HistoriqueAffectationSuperviseur(Base):
    """Journal immuable des affectations de superviseurs aux FS."""

    __tablename__ = "historique_affectations_superviseurs"

    id: Mapped[int] = mapped_column(primary_key=True)
    formation_sanitaire_id: Mapped[int] = mapped_column(
        ForeignKey("formations_sanitaires.id"), nullable=False, index=True
    )
    ancien_superviseur_id: Mapped[int | None] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=True
    )
    nouveau_superviseur_id: Mapped[int | None] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=True
    )
    administrateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    date_operation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class HistoriqueModification(Base):
    __tablename__ = "historique_modifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiche_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fiches_paludisme.id"), nullable=False, index=True
    )
    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False
    )
    date_operation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    ancienne_version: Mapped[int] = mapped_column(Integer, nullable=False)
    nouvelle_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changements: Mapped[dict] = mapped_column(JSON, nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)


class JournalSynchronisation(Base):
    __tablename__ = "journal_synchronisation"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiche_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    statut: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class DemandeCorrection(Base):
    """Demande de correction formulÃ©e par un superviseur."""

    __tablename__ = "demandes_correction"
    __table_args__ = (
        CheckConstraint(
            "statut IN ('ouverte', 'reponse_agent', 'a_corriger', 'acceptee')",
            name="ck_demande_correction_statut",
        ),
        Index("ix_demande_correction_fiche_statut", "fiche_id", "statut"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fiche_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fiches_paludisme.id"),
        nullable=False,
        index=True,
    )
    superviseur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"),
        nullable=False,
        index=True,
    )
    motif: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(
        String(30), default="ouverte", nullable=False
    )
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    modifie_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


class HistoriqueSupervision(Base):
    """Historique des Ã©vÃ©nements d'une demande de correction."""

    __tablename__ = "historique_supervision"

    id: Mapped[int] = mapped_column(primary_key=True)
    demande_id: Mapped[int] = mapped_column(
        ForeignKey("demandes_correction.id"),
        nullable=False,
        index=True,
    )
    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"),
        nullable=False,
        index=True,
    )
    evenement: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


class Notification(Base):
    """Notification interne adressÃ©e Ã  un utilisateur prÃ©cis."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_utilisateur_lue_cree",
            "utilisateur_id",
            "lue_le",
            "cree_le",
        ),
        Index("ix_notifications_fiche_id", "fiche_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    titre: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    fiche_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fiches_paludisme.id"),
        nullable=True,
    )
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    lue_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LivraisonNotification(Base):
    __tablename__ = "livraisons_notifications"
    __table_args__ = (
        CheckConstraint(
            "canal IN ('whatsapp', 'web_push', 'android_push')",
            name="ck_livraison_notification_canal",
        ),
        CheckConstraint(
            "statut IN ('en_attente', 'en_cours', 'envoyee', 'echec')",
            name="ck_livraison_notification_statut",
        ),
        Index(
            "ix_livraisons_notifications_a_traiter",
            "statut",
            "prochaine_tentative",
        ),
        Index("ix_livraisons_notifications_fiche", "fiche_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    fiche_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fiches_paludisme.id", ondelete="SET NULL"),
        nullable=True,
    )
    canal: Mapped[str] = mapped_column(String(20), nullable=False)
    destinataire: Mapped[str] = mapped_column(String(255), nullable=False)
    contenu: Mapped[dict] = mapped_column(JSON, nullable=False)
    statut: Mapped[str] = mapped_column(
        String(20), default="en_attente", nullable=False
    )
    tentatives: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    prochaine_tentative: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    derniere_erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    envoye_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AppareilPush(Base):
    __tablename__ = "appareils_push"
    __table_args__ = (
        UniqueConstraint("jeton", name="uq_appareils_push_jeton"),
        CheckConstraint(
            "plateforme IN ('web', 'android')",
            name="ck_appareils_push_plateforme",
        ),
        Index(
            "ix_appareils_push_utilisateur_actif",
            "utilisateur_id",
            "actif",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="CASCADE"),
        nullable=False,
    )
    jeton: Mapped[str] = mapped_column(Text, nullable=False)
    plateforme: Mapped[str] = mapped_column(String(20), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    mis_a_jour_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint(
            "token_hash",
            name="uq_refresh_tokens_token_hash",
        ),
        Index(
            "ix_refresh_tokens_utilisateur_expiration",
            "utilisateur_id",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="CASCADE"),
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoque_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    remplace_par_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )