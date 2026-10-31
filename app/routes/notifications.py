from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import Notification, Utilisateur, AppareilPush
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)

class EnregistrerAppareilPushSchema(BaseModel):
    jeton: str = Field(min_length=20, max_length=4096)
    plateforme: str = Field(pattern="^(web|android)$")

class DesactiverAppareilPushSchema(BaseModel):
    jeton: str = Field(min_length=20, max_length=4096)

def _serialiser(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "type": notification.type,
        "titre": notification.titre,
        "message": notification.message,
        "fiche_id": str(notification.fiche_id) if notification.fiche_id else None,
        "cree_le": notification.cree_le,
        "lue_le": notification.lue_le,
        "est_lue": notification.lue_le is not None,
    }


@router.get("")
def lister_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    non_lues_seulement: bool = False,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Retourne uniquement les notifications de l'utilisateur connecté."""
    stmt = select(Notification).where(
        Notification.utilisateur_id == utilisateur.id
    )
    if non_lues_seulement:
        stmt = stmt.where(Notification.lue_le.is_(None))

    total = db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0
    items = db.scalars(
        stmt.order_by(Notification.cree_le.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    non_lues = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.utilisateur_id == utilisateur.id,
            Notification.lue_le.is_(None),
        )
    ) or 0

    return {
        "items": [_serialiser(item) for item in items],
        "total": total,
        "non_lues": non_lues,
        "limit": limit,
        "offset": offset,
    }


@router.get("/non-lues/count")
def compter_notifications_non_lues(
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Compte les notifications non lues de l'utilisateur connecté."""
    total = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.utilisateur_id == utilisateur.id,
            Notification.lue_le.is_(None),
        )
    ) or 0
    return {"non_lues": total}


@router.patch("/lues")
def marquer_toutes_comme_lues(
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Marque comme lues les notifications du seul utilisateur connecté."""
    maintenant = datetime.now(timezone.utc)
    resultat = db.execute(
        update(Notification)
        .where(
            Notification.utilisateur_id == utilisateur.id,
            Notification.lue_le.is_(None),
        )
        .values(lue_le=maintenant)
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"marquees_lues": resultat.rowcount or 0}


@router.patch("/{notification_id}/lue")
def marquer_notification_comme_lue(
    notification_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Marque une notification comme lue si elle appartient à l'utilisateur."""
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.utilisateur_id == utilisateur.id,
        )
    )
    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification introuvable.",
        )

    if notification.lue_le is None:
        notification.lue_le = datetime.now(timezone.utc)
        try:
            db.commit()
            db.refresh(notification)
        except Exception:
            db.rollback()
            raise

    return _serialiser(notification)

@router.post("/appareils", status_code=200)
def enregistrer_appareil_push(
    donnees: EnregistrerAppareilPushSchema,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    jeton = donnees.jeton.strip()

    if not jeton:
        raise HTTPException(
            status_code=422,
            detail="Le jeton push est obligatoire.",
        )

    appareil = db.scalar(
        select(AppareilPush).where(
            AppareilPush.jeton == jeton
        )
    )

    if appareil is not None:
        appareil.utilisateur_id = utilisateur.id
        appareil.plateforme = donnees.plateforme
        appareil.actif = True
        appareil.mis_a_jour_le = datetime.now(timezone.utc)
    else:
        appareil = AppareilPush(
            utilisateur_id=utilisateur.id,
            jeton=jeton,
            plateforme=donnees.plateforme,
            actif=True,
        )
        db.add(appareil)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Appareil enregistré avec succès.",
        "plateforme": appareil.plateforme,
        "actif": appareil.actif,
    }

@router.patch("/appareils/desactiver")
def desactiver_appareil_push(
    donnees: DesactiverAppareilPushSchema,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    appareil = db.scalar(
        select(AppareilPush).where(
            AppareilPush.jeton == donnees.jeton.strip(),
            AppareilPush.utilisateur_id == utilisateur.id,
        )
    )

    if appareil is None:
        raise HTTPException(
            status_code=404,
            detail="Appareil non trouvé.",
        )

    appareil.actif = False
    appareil.mis_a_jour_le = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Notifications désactivées sur cet appareil."}