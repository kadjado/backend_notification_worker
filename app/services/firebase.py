
import base64
import binascii
import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings


def obtenir_application_firebase():
    """
    Initialise Firebase Admin une seule fois.

    Priorité :
    1. Variable d'environnement FIREBASE_SERVICE_ACCOUNT_JSON_BASE64
    2. Fichier local firebase-service-account.json
    """
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    secret_base64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_BASE64")

    if secret_base64:
        try:
            contenu_json = base64.b64decode(
                secret_base64,
                validate=True,
            ).decode("utf-8")

            identification_json = json.loads(contenu_json)

            identification = credentials.Certificate(identification_json)

        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            raise ValueError(
                "La variable FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 "
                "ne contient pas un JSON Firebase Base64 valide."
            ) from erreur

    else:
        chemin = Path(settings.firebase_service_account_path)

        if not chemin.is_file():
            raise FileNotFoundError(
                f"Configuration Firebase introuvable : {chemin}. "
                "Définissez FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 "
                "ou fournissez le fichier de service Firebase."
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
