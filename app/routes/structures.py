
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.db.dependencies import get_db
from app.models import Region, Prefecture, Commune, FormationSanitaire
from app.structure_schemas import (
    RegionCreate,
    RegionUpdate,
    RegionResponse,
    PrefectureCreate,
    PrefectureUpdate,
    PrefectureResponse,
    CommuneCreate,
    CommuneUpdate,
    CommuneResponse,
    FormationSanitaireCreate,
    FormationSanitaireUpdate,
    FormationSanitaireResponse,
)

router = APIRouter(
    prefix="/api/v1/admin/structures",
    tags=["Structures sanitaires"],
    dependencies=[Depends(require_roles("administrateur_national"))],
)


def _get_or_404(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} introuvable.",
        )
    return item


def _ensure_code_available(
    db: Session, model, code: str, current_id: int | None = None
):
    query = select(model).where(model.code == code)
    existing = db.scalar(query)

    if existing is not None and existing.id != current_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce code est déjà utilisé.",
        )


def _save(db: Session, item):
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Enregistrement impossible : code déjà utilisé ou relation invalide.",
        ) from None


def _update_item(db: Session, item, changes: dict, model):
    for field, value in changes.items():
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Le champ '{field}' ne peut pas être null.",
            )

        if field == "code":
            _ensure_code_available(db, model, value, item.id)

        setattr(item, field, value)

    return _save(db, item)


# -------------------------------------------------------------------
# REGIONS
# -------------------------------------------------------------------

@router.get("/regions", response_model=list[RegionResponse])
def list_regions(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Region).order_by(Region.libelle).offset(offset).limit(limit)
    ).all()


@router.post(
    "/regions",
    response_model=RegionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_region(data: RegionCreate, db: Session = Depends(get_db)):
    _ensure_code_available(db, Region, data.code)
    return _save(db, Region(code=data.code, libelle=data.libelle))


@router.patch("/regions/{region_id}", response_model=RegionResponse)
def update_region(
    region_id: int,
    data: RegionUpdate,
    db: Session = Depends(get_db),
):
    item = _get_or_404(db, Region, region_id, "Région")
    return _update_item(
        db, item, data.model_dump(exclude_unset=True), Region
    )


# -------------------------------------------------------------------
# PREFECTURES
# -------------------------------------------------------------------

@router.get("/prefectures", response_model=list[PrefectureResponse])
def list_prefectures(
    region_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(Prefecture)

    if region_id is not None:
        query = query.where(Prefecture.region_id == region_id)

    return db.scalars(
        query.order_by(Prefecture.libelle).offset(offset).limit(limit)
    ).all()


@router.post(
    "/prefectures",
    response_model=PrefectureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prefecture(
    data: PrefectureCreate,
    db: Session = Depends(get_db),
):
    _get_or_404(db, Region, data.region_id, "Région")
    _ensure_code_available(db, Prefecture, data.code)

    return _save(
        db,
        Prefecture(
            code=data.code,
            libelle=data.libelle,
            region_id=data.region_id,
        ),
    )


@router.patch(
    "/prefectures/{prefecture_id}",
    response_model=PrefectureResponse,
)
def update_prefecture(
    prefecture_id: int,
    data: PrefectureUpdate,
    db: Session = Depends(get_db),
):
    item = _get_or_404(db, Prefecture, prefecture_id, "Préfecture")
    changes = data.model_dump(exclude_unset=True)

    if changes.get("region_id") is not None:
        _get_or_404(db, Region, changes["region_id"], "Région")

    return _update_item(db, item, changes, Prefecture)


# -------------------------------------------------------------------
# COMMUNES
# -------------------------------------------------------------------

@router.get("/communes", response_model=list[CommuneResponse])
def list_communes(
    prefecture_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(Commune)

    if prefecture_id is not None:
        query = query.where(Commune.prefecture_id == prefecture_id)

    return db.scalars(
        query.order_by(Commune.libelle).offset(offset).limit(limit)
    ).all()


@router.post(
    "/communes",
    response_model=CommuneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_commune(data: CommuneCreate, db: Session = Depends(get_db)):
    _get_or_404(db, Prefecture, data.prefecture_id, "Préfecture")
    _ensure_code_available(db, Commune, data.code)

    return _save(
        db,
        Commune(
            code=data.code,
            libelle=data.libelle,
            prefecture_id=data.prefecture_id,
        ),
    )


@router.patch("/communes/{commune_id}", response_model=CommuneResponse)
def update_commune(
    commune_id: int,
    data: CommuneUpdate,
    db: Session = Depends(get_db),
):
    item = _get_or_404(db, Commune, commune_id, "Commune")
    changes = data.model_dump(exclude_unset=True)

    if changes.get("prefecture_id") is not None:
        _get_or_404(db, Prefecture, changes["prefecture_id"], "Préfecture")

    return _update_item(db, item, changes, Commune)


# -------------------------------------------------------------------
# FORMATIONS SANITAIRES
# -------------------------------------------------------------------

@router.get(
    "/formations-sanitaires",
    response_model=list[FormationSanitaireResponse],
)
def list_formations_sanitaires(
    commune_id: int | None = None,
    actif: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(FormationSanitaire)

    if commune_id is not None:
        query = query.where(
            FormationSanitaire.commune_id == commune_id
        )

    if actif is not None:
        query = query.where(FormationSanitaire.actif == actif)

    return db.scalars(
        query.order_by(FormationSanitaire.libelle)
        .offset(offset)
        .limit(limit)
    ).all()


@router.post(
    "/formations-sanitaires",
    response_model=FormationSanitaireResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_formation_sanitaire(
    data: FormationSanitaireCreate,
    db: Session = Depends(get_db),
):
    _get_or_404(db, Commune, data.commune_id, "Commune")
    _ensure_code_available(db, FormationSanitaire, data.code)

    return _save(
        db,
        FormationSanitaire(
            code=data.code,
            libelle=data.libelle,
            type_fs=data.type_fs,
            commune_id=data.commune_id,
            actif=data.actif,
        ),
    )


@router.patch(
    "/formations-sanitaires/{formation_id}",
    response_model=FormationSanitaireResponse,
)
def update_formation_sanitaire(
    formation_id: int,
    data: FormationSanitaireUpdate,
    db: Session = Depends(get_db),
):
    item = _get_or_404(
        db, FormationSanitaire, formation_id, "Formation sanitaire"
    )
    changes = data.model_dump(exclude_unset=True)

    if changes.get("commune_id") is not None:
        _get_or_404(db, Commune, changes["commune_id"], "Commune")

    return _update_item(db, item, changes, FormationSanitaire)
