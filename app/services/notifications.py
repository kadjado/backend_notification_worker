from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AppareilPush,
    FormationSanitaire,
    FichePaludisme,
    LivraisonNotification,
    Notification,
    Utilisateur,
)


def creer_notification(
    db: Session,
    *,
    utilisateur_id: int,
    type: str,
    titre: str,
    message: str,
    fiche_id=None,
) -> Notification:
    """Ajoute une notification à la transaction courante, sans commit."""
    notification = Notification(
        utilisateur_id=utilisateur_id,
        type=type,
        titre=titre,
        message=message,
        fiche_id=fiche_id,
    )
    db.add(notification)
    return notification


def notifier_superviseurs_pour_fiche(
    db: Session,
    fiche: FichePaludisme,
    formation: FormationSanitaire,
) -> int:
    """Notifie le superviseur actif et pr?pare les livraisons externes."""
    superviseur = db.scalar(
        select(Utilisateur).where(
            Utilisateur.role == "superviseur",
            Utilisateur.actif.is_(True),
            Utilisateur.formation_sanitaire_id == formation.id,
        )
    )
    if superviseur is None:
        return 0

    notification = creer_notification(
        db,
        utilisateur_id=superviseur.id,
        type="fiche_a_valider",
        titre="Nouvelle fiche ? valider",
        message=(
            f"Une nouvelle fiche ({fiche.numero_fiche}) a ?t? saisie "
            f"par un agent de {formation.libelle}."
        ),
        fiche_id=fiche.id,
    )

    # G?n?re l'identifiant de la notification sans valider la transaction.
    db.flush()

    # Aucun d?tail du patient ni num?ro de fiche dans les messages externes.
    contenu_externe = {
        "titre": "Nouvelle fiche ? valider",
        "message": (
            "Une nouvelle fiche n?cessite votre attention. "
            "Connectez-vous ? SCDIP pour la consulter."
        ),
    }

    telephone = (superviseur.telephone or "").strip()
    if telephone:
        db.add(
            LivraisonNotification(
                notification_id=notification.id,
                fiche_id=fiche.id,
                canal="whatsapp",
                destinataire=telephone,
                contenu=dict(contenu_externe),
            )
        )

    appareils = db.scalars(
        select(AppareilPush).where(
            AppareilPush.utilisateur_id == superviseur.id,
            AppareilPush.actif.is_(True),
        )
    ).all()

    for appareil in appareils:
        if appareil.plateforme not in ("web", "android"):
            continue

        db.add(
            LivraisonNotification(
                notification_id=notification.id,
                fiche_id=fiche.id,
                canal=(
                    "web_push"
                    if appareil.plateforme == "web"
                    else "android_push"
                ),
                destinataire=str(appareil.id),
                contenu={
                    **contenu_externe,
                    "plateforme": appareil.plateforme,
                    "jeton": appareil.jeton,
                },
            )
        )

    # Ne pas commit ici : la route de cr?ation de fiche g?re la transaction.
    return 1


def notifier_agent_fiche(
    db: Session,
    *,
    fiche: FichePaludisme,
    type: str,
    titre: str,
    message: str,
) -> Notification:
    """Adresse une notification à l'agent qui a créé la fiche."""
    return creer_notification(
        db,
        utilisateur_id=fiche.agent_id,
        type=type,
        titre=titre,
        message=message,
        fiche_id=fiche.id,
    )


def notifier_superviseur_demande(
    db: Session,
    *,
    superviseur_id: int,
    fiche: FichePaludisme,
    type: str,
    titre: str,
    message: str,
) -> Notification:
    """Adresse une notification au superviseur propriétaire de la demande."""
    return creer_notification(
        db,
        utilisateur_id=superviseur_id,
        type=type,
        titre=titre,
        message=message,
        fiche_id=fiche.id,
    )
