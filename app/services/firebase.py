
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings


def obtenir_application_firebase():
    """
    Initialise Firebase Admin une seule fois.
    Ne réalise aucun envoi de notification.
    """
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    chemin = Path(settings.firebase_service_account_path)

    if not chemin.is_file():
        raise FileNotFoundError(
            f"Fichier de configuration Firebase introuvable : {chemin}"
        )

    identification = credentials.Certificate(str(chemin))

    return firebase_admin.initialize_app(identification)


def verifier_firebase() -> str:
    """
    Vérifie l'initialisation Firebase et retourne le projet configuré.
    """
    application = obtenir_application_firebase()
    return application.project_id

def envoyer_notification_push(
    *,
    jeton: str,
    titre: str,
    message: str,
    donnees: dict | None = None,
) -> str:
    """
    Envoie une notification push via Firebase Cloud Messaging.
    Retourne l'identifiant du message accepté par Firebase.
    """
    application = obtenir_application_firebase()

    donnees_fcm = {
        str(cle): str(valeur)
        for cle, valeur in (donnees or {}).items()
        if valeur is not None
    }

    notification = messaging.Notification(
        title=titre,
        body=message,
    )

    message_fcm = messaging.Message(
        token=jeton,
        notification=notification,
        data=donnees_fcm,
    )

    return messaging.send(
        message_fcm,
        app=application,
    )