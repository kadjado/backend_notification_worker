from datetime import datetime, timezone

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError


from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError


from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import (
    HistoriqueModification,
    DemandeCorrection,
    HistoriqueSupervision,
    Commune,
    FormationSanitaire,
    FichePaludisme,
    Prefecture,
    Region,
    TypeTDR,
    Utilisateur,
)

from app.schemas import (
    FichePaludismeCreate,
    FichePaludismeResponse,
    FichePaludismeUpdate,
)
from app.services.notifications import (
    notifier_agent_fiche,
    notifier_superviseur_demande,
    notifier_superviseurs_pour_fiche,
)



router = APIRouter(
    prefix="/api/v1/fiches",
    tags=["Fiches de paludisme"],
)


def requete_fiches_visibles(db: Session, utilisateur: Utilisateur):
    """Construit une requête limitée au périmètre de l'utilisateur."""
    stmt = (
        select(FichePaludisme)
        .join(
            FormationSanitaire,
            FichePaludisme.formation_sanitaire_id == FormationSanitaire.id,
        )
        .join(Commune, FormationSanitaire.commune_id == Commune.id)
        .join(Prefecture, Commune.prefecture_id == Prefecture.id)
        .join(Region, Prefecture.region_id == Region.id)
        .where(FichePaludisme.supprime_le.is_(None))
    )

    if utilisateur.role == "agent_fs":
        if utilisateur.formation_sanitaire_id is None:
            raise HTTPException(
                status_code=403,
                detail="Aucune formation sanitaire n'est attribuée à cet agent.",
            )
        stmt = stmt.where(
            FormationSanitaire.id == utilisateur.formation_sanitaire_id
        )

    elif utilisateur.role == "superviseur":
        if utilisateur.formation_sanitaire_id is not None:
            stmt = stmt.where(
                FormationSanitaire.id == utilisateur.formation_sanitaire_id
            )
        elif utilisateur.commune_id is not None:
            # Lecture temporaire des anciens comptes territoriaux.
            # Ils n'ont plus de droits de validation/correction/modification.
            stmt = stmt.where(Commune.id == utilisateur.commune_id)
        elif utilisateur.prefecture_id is not None:
            stmt = stmt.where(Prefecture.id == utilisateur.prefecture_id)
        elif utilisateur.region_id is not None:
            stmt = stmt.where(Region.id == utilisateur.region_id)
        else:
            raise HTTPException(
                status_code=403,
                detail="Aucune FS ni aucun périmètre de lecture n'est attribué à ce superviseur.",
            )

    elif utilisateur.role != "administrateur_national":
        raise HTTPException(
            status_code=403,
            detail="Rôle non autorisé à consulter les fiches.",
        )

    return stmt


def exiger_superviseur_affecte_a_fiche(
    utilisateur: Utilisateur,
    fiche: FichePaludisme,
) -> None:
    """Interdit toute action de supervision hors de la FS assignée."""
    if utilisateur.role != "superviseur":
        raise HTTPException(
            status_code=403,
            detail="Seul un superviseur affecté à la FS peut effectuer cette action.",
        )
    if (
        not utilisateur.actif
        or utilisateur.formation_sanitaire_id is None
        or utilisateur.formation_sanitaire_id != fiche.formation_sanitaire_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Seul le superviseur actif affecté à cette formation sanitaire peut effectuer cette action.",
        )


@router.get("/contexte")
def obtenir_contexte_fiche(
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Retourne le contexte géographique attribué à l'agent FS."""

    if utilisateur.role != "agent_fs":
        raise HTTPException(
            status_code=403,
            detail="Seul un agent de formation sanitaire peut créer une fiche.",
        )

    if utilisateur.formation_sanitaire_id is None:
        raise HTTPException(
            status_code=403,
            detail="Aucune formation sanitaire n'est attribuée à cet agent.",
        )

    resultat = db.execute(
        select(
            FormationSanitaire,
            Commune,
            Prefecture,
            Region,
        )
        .join(
            Commune,
            FormationSanitaire.commune_id == Commune.id,
        )
        .join(
            Prefecture,
            Commune.prefecture_id == Prefecture.id,
        )
        .join(
            Region,
            Prefecture.region_id == Region.id,
        )
        .where(
            FormationSanitaire.id == utilisateur.formation_sanitaire_id,
            FormationSanitaire.actif.is_(True),
        )
    ).first()

    if resultat is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "La formation sanitaire attribuée est introuvable, "
                "inactive ou sa localisation est incomplète."
            ),
        )

    formation, commune, prefecture, region = resultat

    types_tdr = db.scalars(
        select(TypeTDR)
        .where(TypeTDR.actif.is_(True))
        .order_by(TypeTDR.libelle)
    ).all()

    return {
        "region": {
            "id": region.id,
            "code": region.code,
            "libelle": region.libelle,
        },
        "prefecture": {
            "id": prefecture.id,
            "code": prefecture.code,
            "libelle": prefecture.libelle,
        },
        "commune": {
            "id": commune.id,
            "code": commune.code,
            "libelle": commune.libelle,
        },
        "formation_sanitaire": {
            "id": formation.id,
            "code": formation.code,
            "libelle": formation.libelle,
            "type_fs": formation.type_fs,
        },
        "types_tdr": [
            {
                "id": item.id,
                "code": item.code,
                "libelle": item.libelle,
            }
            for item in types_tdr
        ],
    }
    
@router.post(
    "",
    response_model=FichePaludismeResponse,
    status_code=status.HTTP_201_CREATED,
)
def creer_fiche(
    data: FichePaludismeCreate,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """CrÃ©e une fiche pour la formation sanitaire attribuÃ©e Ã  l'agent."""
    if utilisateur.role != "agent_fs":
        raise HTTPException(
            status_code=403,
            detail="Seul un agent de formation sanitaire peut crÃ©er une fiche.",
        )

    if utilisateur.formation_sanitaire_id is None:
        raise HTTPException(
            status_code=403,
            detail="Aucune formation sanitaire n'est attribuÃ©e Ã  cet agent.",
        )

    if data.formation_sanitaire_id != utilisateur.formation_sanitaire_id:
        raise HTTPException(
            status_code=403,
            detail="Vous ne pouvez crÃ©er une fiche que pour votre formation sanitaire.",
        )

    formation = db.scalar(
        select(FormationSanitaire)
        .where(
            FormationSanitaire.id == data.formation_sanitaire_id,
            FormationSanitaire.actif.is_(True),
        )
        .with_for_update()
    )
    if formation is None:
        raise HTTPException(
            status_code=422,
            detail="La formation sanitaire est introuvable ou inactive.",
        )

    superviseur_actif = db.scalar(
        select(Utilisateur.id).where(
            Utilisateur.role == "superviseur",
            Utilisateur.actif.is_(True),
            Utilisateur.formation_sanitaire_id == formation.id,
        ).limit(1)
    )

    if superviseur_actif is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Creation impossible : aucun superviseur actif n'est "
                "affecte a cette formation sanitaire. Contactez "
                "l'administrateur national."
            ),
        )

    if data.type_tdr_id is not None:
        type_tdr = db.scalar(
            select(TypeTDR).where(
                TypeTDR.id == data.type_tdr_id,
                TypeTDR.actif.is_(True),
            )
        )
        if type_tdr is None:
            raise HTTPException(
                status_code=422,
                detail="Le type de TDR est introuvable ou inactif.",
            )

    payload = data.model_dump()
    payload["numero_fiche"] = f"PAL-{uuid.uuid4().hex.upper()}"
    payload["agent_id"] = utilisateur.id
    payload["fonction_agent"] = utilisateur.fonction
    payload["validation_confirmee"] = False

    fiche = FichePaludisme(**payload)
    db.add(fiche)

    try:
        # Le flush attribue l’identifiant UUID sans valider la transaction.
        db.flush()
        notifier_superviseurs_pour_fiche(db, fiche, formation)
        db.commit()
        db.refresh(fiche)
    except IntegrityError as exc:
        db.rollback()

        erreur_pg = getattr(exc.orig, "sqlstate", None)
        contrainte = getattr(
            getattr(exc.orig, "diag", None),
            "constraint_name",
            None,
        )

        if (
            erreur_pg == "23505"
            and contrainte == "uq_fiche_fs_date_numoc"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Une fiche existe dÃ©jÃ  pour cette formation sanitaire, "
                    "cette date et ce numÃ©ro OC."
                ),
            ) from exc

        raise HTTPException(
            status_code=500,
            detail="Erreur d'intÃ©gritÃ© lors de l'enregistrement de la fiche.",
        ) from exc


    return fiche


@router.patch("/{fiche_id}", response_model=FichePaludismeResponse)
def modifier_fiche(
    fiche_id: uuid.UUID,
    data: FichePaludismeUpdate,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    # Seuls les agents et les superviseurs territoriaux peuvent modifier.
    roles_autorises = {"agent_fs", "superviseur"}
    if utilisateur.role not in roles_autorises:
        raise HTTPException(
            status_code=403,
            detail="Votre rôle ne permet pas de modifier une fiche.",
        )

    # L'agent doit avoir une formation sanitaire attribuée.
    if (
        utilisateur.role == "agent_fs"
        and utilisateur.formation_sanitaire_id is None
    ):
        raise HTTPException(
            status_code=403,
            detail="Aucune formation sanitaire n'est attribuée à cet agent.",
        )

    # Cette requête conserve le contrôle du périmètre géographique.
    stmt = requete_fiches_visibles(db, utilisateur).where(
        FichePaludisme.id == fiche_id
    )
    fiche = db.scalar(stmt)

    if fiche is None:
        raise HTTPException(
            status_code=404,
            detail="Fiche introuvable dans votre périmètre d'accès.",
        )

    if utilisateur.role == "superviseur":
        exiger_superviseur_affecte_a_fiche(utilisateur, fiche)

    demande_correction = None
    if utilisateur.role == "agent_fs":
        demande_correction = db.scalar(
            select(DemandeCorrection)
            .where(
                DemandeCorrection.fiche_id == fiche.id,
                DemandeCorrection.statut == "a_corriger",
            )
            .order_by(
                DemandeCorrection.cree_le.desc(),
                DemandeCorrection.id.desc(),
            )
            .with_for_update()
        )
        if demande_correction is None:
            raise HTTPException(
                status_code=403,
                detail="Aucune demande de correction active pour cette fiche.",
            )

    # Une fiche validée ne peut plus être modifiée par l'agent.
    if utilisateur.role == "agent_fs" and fiche.validation_confirmee:
        raise HTTPException(
            status_code=403,
            detail=(
                "Cette fiche est validée. Seul un superviseur autorisé "
                "peut la modifier."
            ),
        )

    changements_demandes = data.model_dump(exclude_unset=True)

    if not changements_demandes:
        raise HTTPException(
            status_code=422,
            detail="Au moins un champ doit Ãªtre fourni.",
        )

    # PrÃ©parer les valeurs complÃ¨tes pour valider aussi les champs
    # qui ne figurent pas dans la requÃªte PATCH.
    valeurs_actuelles = {
        champ: getattr(fiche, champ)
        for champ in FichePaludismeCreate.model_fields
    }
    valeurs_actuelles.update(changements_demandes)

    try:
        fiche_validee = FichePaludismeCreate.model_validate(valeurs_actuelles)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_context=False),
        ) from exc

    # Si le type de TDR change, vÃ©rifier qu'il existe et qu'il est actif.
    if (
        "type_tdr_id" in changements_demandes
        and fiche_validee.type_tdr_id is not None
    ):
        type_tdr = db.scalar(
            select(TypeTDR).where(
                TypeTDR.id == fiche_validee.type_tdr_id,
                TypeTDR.actif.is_(True),
            )
        )
        if type_tdr is None:
            raise HTTPException(
                status_code=422,
                detail="Le type de TDR est introuvable ou inactif.",
            )

    valeurs_validees = fiche_validee.model_dump()
    changements = {}

    for champ in changements_demandes:
        ancienne_valeur = getattr(fiche, champ)
        nouvelle_valeur = valeurs_validees[champ]

        if ancienne_valeur != nouvelle_valeur:
            changements[champ] = {
                "avant": jsonable_encoder(ancienne_valeur),
                "apres": jsonable_encoder(nouvelle_valeur),
            }

    # Une requÃªte sans changement rÃ©el ne crÃ©e pas de nouvelle version.
    if not changements:
        return fiche

    ancienne_version = fiche.version

    for champ in changements:
        setattr(fiche, champ, valeurs_validees[champ])


    historique = HistoriqueModification(
        fiche_id=fiche.id,
        utilisateur_id=utilisateur.id,
        ancienne_version=ancienne_version,
        nouvelle_version=ancienne_version + 1,
        changements=changements,
        operation=(
            "modification"
            if utilisateur.role == "agent_fs"
            else "modif_superviseur"
        ),
    )
    db.add(historique)

    if demande_correction is not None:
        demande_correction.statut = "reponse_agent"
        db.add(
            HistoriqueSupervision(
                demande_id=demande_correction.id,
                utilisateur_id=utilisateur.id,
                evenement="reponse_agent",
                details="L'agent a modifié la fiche en réponse à la demande.",
            )
        )
        notifier_superviseur_demande(
            db,
            superviseur_id=demande_correction.superviseur_id,
            fiche=fiche,
            type="reponse_agent",
            titre="Correction effectuée par l'agent",
            message=(
                f"L'agent a modifié la fiche {fiche.numero_fiche} "
                "en réponse à votre demande. Vous pouvez examiner sa réponse."
            ),
        )

    try:
        db.commit()
        db.refresh(fiche)
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Cette fiche a été modifiée simultanément par une autre "
                "opération. Rechargez-la puis réessayez."
            ),
        ) from exc
    except IntegrityError as exc:
        db.rollback()

        erreur_pg = getattr(exc.orig, "sqlstate", None)
        contrainte = getattr(
            getattr(exc.orig, "diag", None),
            "constraint_name",
            None,
        )

        if (
            erreur_pg == "23505"
            and contrainte == "uq_fiche_fs_date_numoc"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Une fiche existe dÃ©jÃ  pour cette formation sanitaire, "
                    "cette date et ce numÃ©ro OC."
                ),
            ) from exc

        raise HTTPException(
            status_code=500,
            detail="Erreur d'intÃ©gritÃ© lors de la modification de la fiche.",
        ) from exc

    return fiche


@router.get("", response_model=list[FichePaludismeResponse])
def lister_fiches(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Liste les fiches non supprimÃ©es dans le pÃ©rimÃ¨tre autorisÃ©."""
    stmt = requete_fiches_visibles(db, utilisateur)
    stmt = (
        stmt.order_by(
            FichePaludisme.date_consultation.desc(),
            FichePaludisme.cree_le.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()




@router.get("/paginees")
def lister_fiches_paginees(
    search: str = Query(default="", max_length=100),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Recherche et pagination des fiches dans le périmètre autorisé."""
    stmt = requete_fiches_visibles(db, utilisateur)
    terme = search.strip()

    if terme:
        motif = f"%{terme}%"
        stmt = stmt.where(
            or_(
                FichePaludisme.numero_fiche.ilike(motif),
                FichePaludisme.num_oc.ilike(motif),
                FichePaludisme.diagnostic.ilike(motif),
                FichePaludisme.sexe.ilike(motif),
                cast(FichePaludisme.formation_sanitaire_id, String).ilike(motif),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0

    stmt = stmt.order_by(
        FichePaludisme.date_consultation.desc(),
        FichePaludisme.cree_le.desc(),
    ).offset(offset).limit(limit)

    return {
        "items": db.scalars(stmt).all(),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "/{fiche_id}/valider",
    response_model=FichePaludismeResponse,
)
def valider_fiche(
    fiche_id: uuid.UUID,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Valide une fiche dans le périmètre du superviseur autorisé."""
    if utilisateur.role != "superviseur":
        raise HTTPException(
            status_code=403,
            detail="Seul le superviseur affecté à la formation sanitaire peut valider une fiche.",
        )

    stmt = requete_fiches_visibles(db, utilisateur).where(
        FichePaludisme.id == fiche_id
    )
    fiche = db.scalar(stmt)

    if fiche is None:
        raise HTTPException(
            status_code=404,
            detail="Fiche introuvable dans votre périmètre d'accès.",
        )

    exiger_superviseur_affecte_a_fiche(utilisateur, fiche)

    if fiche.validation_confirmee:
        raise HTTPException(
            status_code=409,
            detail="Cette fiche a déjà été validée.",
        )

    ancienne_version = fiche.version
    date_validation = datetime.now(timezone.utc)

    fiche.validation_confirmee = True
    fiche.validee_par_id = utilisateur.id
    fiche.validee_le = date_validation

    historique = HistoriqueModification(
        fiche_id=fiche.id,
        utilisateur_id=utilisateur.id,
        ancienne_version=ancienne_version,
        nouvelle_version=ancienne_version + 1,
        changements={
            "validation_confirmee": {
                "avant": False,
                "apres": True,
            },
            "validee_par_id": {
                "avant": None,
                "apres": utilisateur.id,
            },
            "validee_le": {
                "avant": None,
                "apres": date_validation.isoformat(),
            },
        },
        operation="validation",
    )
    db.add(historique)
    notifier_agent_fiche(
        db,
        fiche=fiche,
        type="fiche_validee",
        titre="Fiche validée",
        message=(
            f"Votre fiche {fiche.numero_fiche} a été validée par le superviseur de votre formation sanitaire."
        ),
    )

    try:
        db.commit()
        db.refresh(fiche)
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Cette fiche a été modifiée simultanément. "
                "Rechargez-la avant de réessayer."
            ),
        ) from exc

    return fiche


@router.post("/{fiche_id}/demander-correction")
def demander_correction(
    fiche_id: uuid.UUID,
    motif: str = Body(..., embed=True, max_length=2000),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Demande une correction avec motif obligatoire."""
    if utilisateur.role != "superviseur":
        raise HTTPException(
            status_code=403,
            detail="Seul le superviseur affecté à la FS peut demander une correction.",
        )

    motif = motif.strip()
    if not motif:
        raise HTTPException(
            status_code=422,
            detail="Le motif de correction est obligatoire.",
        )

    fiche = db.scalar(
        requete_fiches_visibles(db, utilisateur).where(
            FichePaludisme.id == fiche_id
        )
    )
    if fiche is None:
        raise HTTPException(
            status_code=404,
            detail="Fiche introuvable dans votre périmètre d'accès.",
        )
    exiger_superviseur_affecte_a_fiche(utilisateur, fiche)

    if fiche.validation_confirmee:
        raise HTTPException(
            status_code=409,
            detail="Une fiche validée ne peut pas être renvoyée à l'agent.",
        )

    existante = db.scalar(
        select(DemandeCorrection.id).where(
            DemandeCorrection.fiche_id == fiche.id,
            DemandeCorrection.statut.in_(["ouverte", "a_corriger", "reponse_agent"]),
        ).limit(1)
    )
    if existante is not None:
        raise HTTPException(
            status_code=409,
            detail="Une demande de correction est déjà en attente.",
        )

    demande = DemandeCorrection(
        fiche_id=fiche.id,
        superviseur_id=utilisateur.id,
        motif=motif,
        statut="a_corriger",
    )
    db.add(demande)

    try:
        db.flush()
        db.add(
            HistoriqueSupervision(
                demande_id=demande.id,
                utilisateur_id=utilisateur.id,
                evenement="demande_correction",
                details=motif,
            )
        )
        notifier_agent_fiche(
            db,
            fiche=fiche,
            type="correction_demandee",
            titre="Correction demandée",
            message=(
                f"Une correction est demandée pour la fiche {fiche.numero_fiche}. "
                f"Motif : {motif}"
            ),
        )
        db.commit()
        db.refresh(demande)
    except Exception:
        db.rollback()
        raise

    return {
        "id": demande.id,
        "fiche_id": str(demande.fiche_id),
        "motif": demande.motif,
        "statut": demande.statut,
        "cree_le": demande.cree_le,
    }


@router.post("/{fiche_id}/traiter-correction")
def traiter_correction(
    fiche_id: uuid.UUID,
    decision: str = Body(..., embed=True),
    motif: str = Body(default="", embed=True, max_length=2000),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Accepte la correction ou demande une nouvelle correction."""
    if utilisateur.role != "superviseur":
        raise HTTPException(
            status_code=403,
            detail="Seul le superviseur affecté à la FS peut traiter une correction.",
        )

    decision = decision.strip().lower()
    motif = motif.strip()

    if decision not in {"acceptee", "a_corriger"}:
        raise HTTPException(
            status_code=422,
            detail="La décision doit être 'acceptee' ou 'a_corriger'.",
        )

    if decision == "a_corriger" and not motif:
        raise HTTPException(
            status_code=422,
            detail="Un motif est obligatoire pour demander une nouvelle correction.",
        )

    fiche = db.scalar(
        requete_fiches_visibles(db, utilisateur).where(
            FichePaludisme.id == fiche_id
        )
    )
    if fiche is None:
        raise HTTPException(
            status_code=404,
            detail="Fiche introuvable dans votre périmètre d'accès.",
        )

    exiger_superviseur_affecte_a_fiche(utilisateur, fiche)

    if fiche.validation_confirmee:
        raise HTTPException(
            status_code=409,
            detail="Cette fiche est déjà validée.",
        )

    demande = db.scalar(
        select(DemandeCorrection)
        .where(
            DemandeCorrection.fiche_id == fiche.id,
            DemandeCorrection.statut == "reponse_agent",
        )
        .order_by(
            DemandeCorrection.cree_le.desc(),
            DemandeCorrection.id.desc(),
        )
        .with_for_update()
    )

    if demande is None:
        raise HTTPException(
            status_code=409,
            detail="Aucune réponse de l'agent n'est en attente de traitement.",
        )

    if decision == "acceptee":
        demande.statut = "acceptee"
        evenement = "correction_acceptee"
        details = "Le superviseur a accepté la correction."
    else:
        demande.statut = "a_corriger"
        demande.motif = motif
        evenement = "nouvelle_correction_demandee"
        details = motif

    demande.modifie_le = datetime.now().astimezone()

    db.add(
        HistoriqueSupervision(
            demande_id=demande.id,
            utilisateur_id=utilisateur.id,
            evenement=evenement,
            details=details,
        )
    )

    if decision == "acceptee":
        notifier_agent_fiche(
            db,
            fiche=fiche,
            type="correction_acceptee",
            titre="Correction acceptée",
            message=(
                f"Votre correction de la fiche {fiche.numero_fiche} a été acceptée. "
                "La fiche n'est pas automatiquement validée : une validation "
                "distincte reste nécessaire."
            ),
        )
    else:
        notifier_agent_fiche(
            db,
            fiche=fiche,
            type="nouvelle_correction",
            titre="Nouvelle correction demandée",
            message=(
                f"Une nouvelle correction est demandée pour la fiche "
                f"{fiche.numero_fiche}. Motif : {motif}"
            ),
        )

    try:
        db.commit()
        db.refresh(demande)
    except Exception:
        db.rollback()
        raise

    return {
        "id": demande.id,
        "fiche_id": str(demande.fiche_id),
        "statut": demande.statut,
        "motif": demande.motif,
        "modifie_le": demande.modifie_le,
    }


@router.get("/{fiche_id}", response_model=FichePaludismeResponse)
def consulter_fiche(
    fiche_id: uuid.UUID,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Consulte une fiche uniquement si elle appartient au pÃ©rimÃ¨tre autorisÃ©."""
    stmt = requete_fiches_visibles(db, utilisateur).where(
        FichePaludisme.id == fiche_id
    )
    fiche = db.scalar(stmt)

    if fiche is None:
        raise HTTPException(
            status_code=404,
            detail="Fiche introuvable dans votre pÃ©rimÃ¨tre d'accÃ¨s.",
        )

    return fiche

@router.delete("/{fiche_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_fiche(
    fiche_id: uuid.UUID,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """Supprime logiquement une fiche sans effacer son historique."""

    # Seul l'administrateur national peut supprimer une fiche.
    if utilisateur.role != "administrateur_national":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul l'administrateur national peut supprimer une fiche.",
        )

    fiche = db.scalar(
        select(FichePaludisme)
        .where(
            FichePaludisme.id == fiche_id,
            FichePaludisme.supprime_le.is_(None),
        )
        .with_for_update()
    )

    if fiche is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fiche introuvable ou déjà supprimée.",
        )

    fiche.supprime_le = datetime.now(timezone.utc)

    db.add(
        HistoriqueModification(
            fiche_id=fiche.id,
            utilisateur_id=utilisateur.id,
            ancienne_version=fiche.version,
            nouvelle_version=fiche.version + 1,
            changements={
                "supprime_le": {
                    "avant": None,
                    "apres": fiche.supprime_le.isoformat(),
                }
            },
            operation="suppression",
        )
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return None