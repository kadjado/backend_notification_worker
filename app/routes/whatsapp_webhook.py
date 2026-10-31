import hmac
import hashlib
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response
from app.core.config import settings

router = APIRouter(
    prefix="/api/v1/webhooks/whatsapp",
    tags=["Webhook WhatsApp"],
)

logger = logging.getLogger(__name__)


@router.get("")
def verifier_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    """Verification initiale du webhook par Meta."""
    secret = settings.meta_whatsapp_verify_token

    if (
        mode == "subscribe"
        and secret
        and token
        and hmac.compare_digest(token, secret)
        and challenge is not None
    ):
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification webhook refusee")


@router.post("")
async def recevoir_evenement(request: Request):
    """Reception passive des evenements, sans action metier."""
    corps = await request.body()

    # La signature Meta est verifiee lorsque l'App Secret est configure.
    app_secret = getattr(settings, "meta_whatsapp_app_secret", None)
    signature = request.headers.get("X-Hub-Signature-256")

    if not app_secret or not signature or not signature.startswith("sha256="):
        raise HTTPException(
            status_code=401,
            detail="Signature webhook absente ou configuration incomplete",
        )

    digest = hmac.new(
        app_secret.encode("utf-8"),
        corps,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, "sha256=" + digest):
        raise HTTPException(status_code=401, detail="Signature webhook invalide")

    try:
        evenement = json.loads(corps)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON invalide")

    # Ne pas journaliser le corps : il pourrait contenir des donnees personnelles.
    logger.info(
        "Evenement WhatsApp recu; objet=%s",
        evenement.get("object", "inconnu"),
    )

    return {"status": "received"}
