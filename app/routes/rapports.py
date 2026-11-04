from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import FichePaludisme, Utilisateur
from app.routes.fiches import requete_fiches_visibles


router = APIRouter(
    prefix="/api/v1/rapports",
    tags=["Rapports et statistiques"],
)


def obtenir_repartition(db: Session, table, colonne: str) -> dict:
    """Retourne la répartition d'une colonne avec ses valeurs réelles."""
    champ = getattr(table.c, colonne)

    resultats = db.execute(
        select(champ, func.count())
        .select_from(table)
        .group_by(champ)
        .order_by(champ)
    ).all()

    return {
        str(valeur) if valeur is not None else "Non renseigné": nombre
        for valeur, nombre in resultats
    }


@router.get("/statistiques")
def obtenir_statistiques(
    date_debut: date | None = Query(default=None),
    date_fin: date | None = Query(default=None),
    periodicite: Literal["jour", "semaine", "mois", "annee"] = Query(
        default="mois"
    ),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_current_user),
):
    """
    Produit les statistiques épidémiologiques des fiches actives
    accessibles à l'utilisateur connecté.
    """

    if date_debut and date_fin and date_debut > date_fin:
        raise HTTPException(
            status_code=422,
            detail="La date de début doit précéder ou être égale à la date de fin.",
        )

    # Réutilisation des autorisations géographiques existantes.
    requete = requete_fiches_visibles(db, utilisateur)

    if date_debut:
        requete = requete.where(
            FichePaludisme.date_consultation >= date_debut
        )

    if date_fin:
        requete = requete.where(
            FichePaludisme.date_consultation <= date_fin
        )

    fiches = requete.order_by(None).subquery()

    # Nombre total de fiches, tous diagnostics confondus.
    total = db.scalar(
        select(func.count()).select_from(fiches)
    ) or 0

    # Répartition des diagnostics.
    diagnostics = obtenir_repartition(db, fiches, "diagnostic")

    # Répartition des issues d'hospitalisation.
    issues = obtenir_repartition(
        db, fiches, "issue_hospitalisation"
    )

    # Répartition des valeurs de grossesse réellement enregistrées.
    grossesses = obtenir_repartition(db, fiches, "grossesse")

    # Répartition des résultats TDR réellement enregistrés.
    resultats_tdr = obtenir_repartition(
        db, fiches, "resultat_tdr"
    )

    # Répartition par sexe.
    sexes = obtenir_repartition(db, fiches, "sexe")

    # Hospitalisations et examens.
    hospitalises = db.scalar(
        select(func.count())
        .select_from(fiches)
        .where(fiches.c.hospitalise.is_(True))
    ) or 0

    tdr_realises = db.scalar(
        select(func.count())
        .select_from(fiches)
        .where(fiches.c.tdr_realise.is_(True))
    ) or 0

    # Les issues clôturées excluent les dossiers encore en cours
    # et ceux dont l'issue n'est pas renseignée.
    issues_cloturees = (
        (issues.get("Guéri", 0))
        + (issues.get("Transféré", 0))
        + (issues.get("Décédé", 0))
        + (issues.get("Sorti contre avis", 0))
    )

    guerisons = issues.get("Guéri", 0)
    deces = issues.get("Décédé", 0)

    taux_guerison = (
        round(guerisons * 100 / issues_cloturees, 2)
        if issues_cloturees else 0
    )

    taux_deces = (
        round(deces * 100 / issues_cloturees, 2)
        if issues_cloturees else 0
    )

    # Regroupement chronologique.
    periodicites_sql = {
        "jour": "day",
        "semaine": "week",
        "mois": "month",
        "annee": "year",
    }

    periode_sql = func.date_trunc(
        periodicites_sql[periodicite],
        fiches.c.date_consultation,
    )

    series = db.execute(
        select(
            periode_sql.label("periode"),
            func.count().label("total"),
        )
        .select_from(fiches)
        .group_by(periode_sql)
        .order_by(periode_sql)
    ).all()

    evolution = [
        {
            "periode": periode.isoformat(),
            "total": nombre,
        }
        for periode, nombre in series
    ]

    return {
        "filtres": {
            "date_debut": date_debut,
            "date_fin": date_fin,
            "periodicite": periodicite,
        },
        "indicateurs": {
            "total_fiches": total,
            "paludisme_simple": diagnostics.get(
                "Paludisme simple", 0
            ),
            "paludisme_grave": diagnostics.get(
                "Paludisme grave", 0
            ),
            "non_confirmes": diagnostics.get(
                "Non confirmé", 0
            ),
            "autres_diagnostics": diagnostics.get("Autre", 0),
            "cas_confirmes": (
                diagnostics.get("Paludisme simple", 0)
                + diagnostics.get("Paludisme grave", 0)
            ),
            "hospitalisations": hospitalises,
            "tdr_realises": tdr_realises,
            "guerisons_hospitalisation": guerisons,
            "deces_hospitalisation": deces,
            "issues_hospitalisation_cloturees": issues_cloturees,
            "taux_guerison_issues_cloturees": taux_guerison,
            "taux_deces_issues_cloturees": taux_deces,
        },
        "repartitions": {
            "diagnostics": diagnostics,
            "issues_hospitalisation": issues,
            "grossesses": grossesses,
            "resultats_tdr": resultats_tdr,
            "sexes": sexes,
        },
        "evolution": evolution,
    }