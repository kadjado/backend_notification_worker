"""Worker indépendant pour les livraisons WhatsApp et Push de SCDIP."""

import logging
import signal
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, text

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models import AppareilPush, LivraisonNotification
from app.services.firebase import envoyer_notification_push


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scdip.notifications")

BATCH_SIZE = 10
MAX_ATTEMPTS = 8
POLL_SECONDS = 5
HTTP_TIMEOUT_SECONDS = 15
ADVISORY_LOCK_ID = 72819462031

class ErreurHTTPMeta(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Erreur API Meta HTTP {status_code}.")

stop_requested = False


def request_stop(signum, frame):
    global stop_requested
    stop_requested = True


def canaux_configures() -> set[str]:
    """Retourne les canaux dont la configuration est disponible."""
    canaux = set()

    if (
        settings.meta_whatsapp_access_token
        and settings.meta_whatsapp_phone_number_id
        and settings.meta_whatsapp_template_name
    ):
        canaux.add("whatsapp")
    else:
        logger.warning(
            "WhatsApp désactivé : configuration Meta incomplète."
        )

    chemin_firebase = settings.firebase_service_account_path
    if chemin_firebase.is_file():
        canaux.update({"web_push", "android_push"})
    else:
        logger.warning(
            "Push désactivé : compte de service Firebase introuvable (%s).",
            chemin_firebase,
        )

    return canaux


def envoyer_whatsapp(destinataire: str) -> None:
    """Envoie un modèle WhatsApp approuvé sans paramètres obligatoires."""
    numero = "".join(
        caractere for caractere in destinataire if caractere.isdigit()
    )

    if not numero or len(numero) < 8 or len(numero) > 15:
        raise ValueError("Numéro destinataire invalide.")

    version = settings.meta_whatsapp_graph_api_version.strip()
    if not version.startswith("v") or "/" in version:
        raise ValueError("Version Graph API invalide.")

    url = (
        f"https://graph.facebook.com/{version}/"
        f"{settings.meta_whatsapp_phone_number_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": settings.meta_whatsapp_template_name,
            "language": {
                "code": settings.meta_whatsapp_template_language,
            },
        },
    }

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.post(
            url,
            headers={
                "Authorization": (
                    f"Bearer {settings.meta_whatsapp_access_token}"
                ),
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.is_success:
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Réponse Meta illisible après la requête."
            ) from exc

        messages = data.get("messages", [])
        if not messages or not messages[0].get("id"):
            raise RuntimeError(
                "Meta n'a pas confirmé la création du message."
            )
        return

    raise ErreurHTTPMeta(response.status_code)


def obtenir_appareil_et_jeton(
    destinataire: str,
    contenu: dict,
) -> tuple[int | None, str, str]:
    """
    Récupère le jeton FCM courant.
    Compatibilité conservée avec les anciennes livraisons contenant
    directement le jeton dans leur contenu JSON.
    """
    try:
        appareil_id = int(destinataire)
    except (TypeError, ValueError):
        appareil_id = None

    if appareil_id is not None:
        with SessionLocal() as db:
            appareil = db.get(AppareilPush, appareil_id)

            if appareil is not None:
                if not appareil.actif:
                    raise ValueError("Appareil Push désactivé.")

                if appareil.plateforme not in ("web", "android"):
                    raise ValueError("Plateforme Push invalide.")

                if not appareil.jeton:
                    raise ValueError("Jeton FCM absent.")

                return appareil.id, appareil.jeton, appareil.plateforme

    # Anciennes livraisons créées avant la centralisation.
    jeton_ancien = contenu.get("jeton")
    plateforme = contenu.get("plateforme")

    if jeton_ancien and plateforme in ("web", "android"):
        return appareil_id, str(jeton_ancien), str(plateforme)

    raise ValueError("Appareil ou jeton Push introuvable.")


def envoyer_push(
    canal: str,
    destinataire: str,
    contenu: dict,
) -> None:
    """Envoie une notification FCM Web ou Android."""
    appareil_id, jeton, plateforme = obtenir_appareil_et_jeton(
        destinataire,
        contenu,
    )

    plateforme_attendue = (
        "web" if canal == "web_push" else "android"
    )

    if plateforme != plateforme_attendue:
        raise ValueError(
            "La plateforme de l'appareil ne correspond pas au canal."
        )

    titre = str(contenu.get("titre") or "SCDIP - PNLP")
    message = str(
        contenu.get("message")
        or "Vous avez une nouvelle notification. Connectez-vous à SCDIP."
    )

    donnees = {
        "notification_id": str(contenu.get("notification_id") or ""),
        "type": str(contenu.get("type") or "notification"),
        "url": "/",
    }

    try:
        envoyer_notification_push(
            jeton=jeton,
            titre=titre,
            message=message,
            donnees=donnees,
        )
    except Exception as exc:
        # Une erreur FCM UNREGISTERED indique que le jeton n'est plus valide.
        code = str(getattr(exc, "code", "") or "").lower()
        nom = type(exc).__name__.lower()

        jeton_invalide = (
            "unregistered" in code
            or "unregistered" in nom
            or "sender_id_mismatch" in code
            or "senderidmismatch" in nom
        )

        if jeton_invalide and appareil_id is not None:
            with SessionLocal() as db:
                appareil = db.get(AppareilPush, appareil_id)
                if appareil is not None:
                    appareil.actif = False
                    appareil.mis_a_jour_le = datetime.now(timezone.utc)
                    db.commit()

            raise ValueError(
                "Jeton FCM invalide : appareil désactivé."
            ) from exc

        raise


def delai_reessai(tentative: int) -> timedelta:
    secondes = min(
        30 * (2 ** max(tentative - 1, 0)),
        6 * 60 * 60,
    )
    return timedelta(seconds=secondes)


def recuperer_livraisons(
    canaux: set[str],
) -> list[tuple[int, str, str, int, dict]]:
    """Réserve un lot de livraisons disponibles avec SKIP LOCKED."""
    if not canaux:
        return []

    maintenant = datetime.now(timezone.utc)

    with SessionLocal() as db:
        lignes = db.scalars(
            select(LivraisonNotification)
            .where(
                LivraisonNotification.canal.in_(canaux),
                LivraisonNotification.statut == "en_attente",
                LivraisonNotification.prochaine_tentative <= maintenant,
            )
            .order_by(
                LivraisonNotification.prochaine_tentative,
                LivraisonNotification.id,
            )
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        ).all()

        reservees = []

        for ligne in lignes:
            ligne.statut = "en_cours"
            ligne.tentatives += 1

            reservees.append(
                (
                    ligne.id,
                    ligne.canal,
                    ligne.destinataire,
                    ligne.tentatives,
                    dict(ligne.contenu or {}),
                )
            )

        db.commit()
        return reservees


def enregistrer_echec(
    livraison_id: int,
    tentative: int,
    erreur: str,
    *,
    reessayable: bool,
) -> None:
    with SessionLocal() as db:
        ligne = db.get(LivraisonNotification, livraison_id)

        if ligne is None:
            logger.error("Livraison %s introuvable.", livraison_id)
            return

        ligne.derniere_erreur = erreur[:500]

        if reessayable and tentative < MAX_ATTEMPTS:
            ligne.statut = "en_attente"
            ligne.prochaine_tentative = (
                datetime.now(timezone.utc) + delai_reessai(tentative)
            )
        else:
            ligne.statut = "echec"

        db.commit()


def traiter_livraison(
    livraison_id: int,
    canal: str,
    destinataire: str,
    tentative: int,
    contenu: dict,
) -> None:
    try:
        if canal == "whatsapp":
            envoyer_whatsapp(destinataire)

        elif canal in ("web_push", "android_push"):
            envoyer_push(canal, destinataire, contenu)

        else:
            raise ValueError(f"Canal non pris en charge : {canal}")

    except httpx.HTTPError:
        # Pour WhatsApp, une erreur réseau peut survenir après acceptation
        # par Meta. On évite donc un renvoi potentiellement en double.
        if canal == "whatsapp":
            enregistrer_echec(
                livraison_id,
                tentative,
                "Erreur réseau ; résultat d'envoi incertain, vérification requise.",
                reessayable=False,
            )
        else:
            enregistrer_echec(
                livraison_id,
                tentative,
                "Erreur réseau pendant l'envoi Push.",
                reessayable=True,
            )

        logger.warning(
            "Erreur réseau livraison %s (%s).",
            livraison_id,
            canal,
        )
        return
    except ErreurHTTPMeta as exc:
        enregistrer_echec(
            livraison_id,
            tentative,
            str(exc),
            reessayable=(
                (
                    exc.status_code in (408, 425, 429)
                    or exc.status_code >= 500
                )
                and tentative < MAX_ATTEMPTS
            ),
        )
        logger.warning(
            "Erreur Meta HTTP %s pour la livraison %s.",
            exc.status_code,
            livraison_id,
        )
        return
    except ValueError as exc:
        enregistrer_echec(
            livraison_id,
            tentative,
            str(exc),
            reessayable=False,
        )
        logger.warning(
            "Échec définitif livraison %s (%s) : %s",
            livraison_id,
            canal,
            exc,
        )
        return

    except Exception as exc:
        code = str(getattr(exc, "code", "") or "").lower()

        # Les erreurs Firebase temporaires sont réessayées.
        codes_temporaires = (
            "unavailable",
            "internal",
            "quota_exceeded",
            "third_party_auth_error",
            "deadline_exceeded",
            "resource_exhausted",
        )

        reessayable = canal in ("web_push", "android_push") and any(
            valeur in code for valeur in codes_temporaires
        )

        enregistrer_echec(
            livraison_id,
            tentative,
            f"Erreur fournisseur {canal} : {type(exc).__name__}.",
            reessayable=reessayable,
        )

        logger.exception(
            "Erreur livraison %s (%s).",
            livraison_id,
            canal,
        )
        return

    with SessionLocal() as db:
        ligne = db.get(LivraisonNotification, livraison_id)

        if ligne is None:
            logger.error(
                "Livraison %s introuvable après envoi.",
                livraison_id,
            )
            return

        ligne.statut = "envoyee"
        ligne.envoye_le = datetime.now(timezone.utc)
        ligne.derniere_erreur = None
        db.commit()

    logger.info(
        "Livraison %s (%s) acceptée par le fournisseur.",
        livraison_id,
        canal,
    )


def main() -> int:
    canaux = canaux_configures()

    if not canaux:
        logger.error(
            "Worker non démarré : aucun canal WhatsApp ou Push configuré."
        )
        return 2

    signal.signal(signal.SIGINT, request_stop)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    # Garder cette connexion ouverte : le verrou est lié à la session SQL.
    with engine.connect() as verrou:
        obtenu = verrou.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": ADVISORY_LOCK_ID},
        ).scalar()

        verrou.commit()

        if not obtenu:
            logger.error("Une autre instance du worker est déjà active.")
            return 3

        try:
            # Les livraisons interrompues ne sont pas renvoyées aveuglément :
            # le fournisseur a peut-être déjà accepté l'envoi.
            with SessionLocal() as db:
                db.execute(
                    text(
                        "UPDATE livraisons_notifications "
                        "SET statut = 'echec', "
                        "derniere_erreur = "
                        "'Interruption du worker : résultat incertain ; "
                        "vérification manuelle requise.', "
                        "prochaine_tentative = now() "
                        "WHERE statut = 'en_cours'"
                    )
                )
                db.commit()

            logger.info(
                "Worker démarré. Canaux actifs : %s",
                ", ".join(sorted(canaux)),
            )

            while not stop_requested:
                lot = recuperer_livraisons(canaux)

                if not lot:
                    time.sleep(POLL_SECONDS)
                    continue

                for (
                    livraison_id,
                    canal,
                    destinataire,
                    tentative,
                    contenu,
                ) in lot:
                    if stop_requested:
                        break

                    try:
                        traiter_livraison(
                            livraison_id,
                            canal,
                            destinataire,
                            tentative,
                            contenu,
                        )
                    except Exception:
                        logger.exception(
                            "Erreur locale sur la livraison %s.",
                            livraison_id,
                        )

            logger.info("Arrêt du worker demandé.")
            return 0

        finally:
            try:
                verrou.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": ADVISORY_LOCK_ID},
                )
                verrou.commit()
            except Exception:
                logger.exception(
                    "Impossible de libérer le verrou proprement."
                )


if __name__ == "__main__":
    raise SystemExit(main())

