
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import (
    Utilisateur,
    Region,
    Prefecture,
    Commune,
    FormationSanitaire,
    HistoriquePermutationAffectation,
    HistoriqueAffectationSuperviseur,
)

from app.auth_schemas import AuthenticatedUser
from app.admin_schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
    PermutationAffectationsRequest,
    PermutationAffectationsResponse,
    AffectationSuperviseurFSRequest,
)
from app.core.dependencies import require_roles
from app.core.security import hash_password
from app.db.dependencies import get_db


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Administration"],
)

admin_only = require_roles("administrateur_national")


def normaliser_perimetre(db: Session, role: str, scope: dict) -> dict:
    """Valide et normalise le rattachement territorial selon le rôle."""

    region_id = scope.get("region_id")
    prefecture_id = scope.get("prefecture_id")
    commune_id = scope.get("commune_id")
    formation_id = scope.get("formation_sanitaire_id")

    def verifier_parent(champ: str, fourni, attendu):
        if fourni is not None and fourni != attendu:
            raise HTTPException(
                status_code=422,
                detail=f"Le champ '{champ}' ne correspond pas à la structure sélectionnée.",
            )

    def resultat(fs=None, commune=None, prefecture=None, region=None):
        return {
            "formation_sanitaire_id": fs,
            "commune_id": commune,
            "prefecture_id": prefecture,
            "region_id": region,
        }

    if role == "administrateur_national":
        return resultat()

    if role == "agent_fs":
        if formation_id is None:
            raise HTTPException(
                status_code=422,
                detail="Un agent FS doit être rattaché à une formation sanitaire.",
            )

        fs = db.get(FormationSanitaire, formation_id)
        if fs is None or not fs.actif:
            raise HTTPException(
                status_code=422,
                detail="Formation sanitaire introuvable ou inactive.",
            )

        commune = db.get(Commune, fs.commune_id)
        if commune is None:
            raise HTTPException(status_code=422, detail="Commune de la FS introuvable.")

        prefecture = db.get(Prefecture, commune.prefecture_id)
        if prefecture is None:
            raise HTTPException(status_code=422, detail="Préfecture de la FS introuvable.")

        region = db.get(Region, prefecture.region_id)
        if region is None:
            raise HTTPException(status_code=422, detail="Région de la FS introuvable.")

        verifier_parent("commune_id", commune_id, commune.id)
        verifier_parent("prefecture_id", prefecture_id, prefecture.id)
        verifier_parent("region_id", region_id, region.id)

        return resultat(fs.id, commune.id, prefecture.id, region.id)

    if role == "superviseur":
        if formation_id is not None:
            fs = db.get(FormationSanitaire, formation_id)

            if fs is None or not fs.actif:
                raise HTTPException(
                    status_code=422,
                    detail="Formation sanitaire introuvable ou inactive.",
                )

            # Les valeurs territoriales saisies sont volontairement ignorées.
            return resultat(fs=fs.id)

        # Compatibilité avec les anciens superviseurs territoriaux.
        if commune_id is not None:
            commune = db.get(Commune, commune_id)
            if commune is None:
                raise HTTPException(status_code=422, detail="Commune introuvable.")

            prefecture = db.get(Prefecture, commune.prefecture_id)
            if prefecture is None:
                raise HTTPException(status_code=422, detail="Préfecture introuvable.")

            region = db.get(Region, prefecture.region_id)
            if region is None:
                raise HTTPException(status_code=422, detail="Région introuvable.")

            verifier_parent("prefecture_id", prefecture_id, prefecture.id)
            verifier_parent("region_id", region_id, region.id)

            return resultat(
                commune=commune.id,
                prefecture=prefecture.id,
                region=region.id,
            )

        if prefecture_id is not None:
            prefecture = db.get(Prefecture, prefecture_id)
            if prefecture is None:
                raise HTTPException(status_code=422, detail="Préfecture introuvable.")

            region = db.get(Region, prefecture.region_id)
            if region is None:
                raise HTTPException(status_code=422, detail="Région introuvable.")

            verifier_parent("region_id", region_id, region.id)

            return resultat(
                prefecture=prefecture.id,
                region=region.id,
            )

        if region_id is not None:
            if db.get(Region, region_id) is None:
                raise HTTPException(status_code=422, detail="Région introuvable.")

            return resultat(region=region_id)

        return resultat()

    raise HTTPException(
        status_code=422,
        detail="Rôle utilisateur non reconnu.",
    )


@router.get("/me", response_model=AuthenticatedUser)
def get_admin_profile(
    current_user: Utilisateur = Depends(admin_only),
) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=current_user.id,
        nom=current_user.nom,
        prenom=current_user.prenom,
        email=current_user.email,
        role=current_user.role,
    )


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
) -> AdminUserResponse:
    
    email = data.email.strip().lower()

    # Vérifier si l'adresse email existe déjà
    existing = db.scalar(
        select(Utilisateur.id).where(
            Utilisateur.email == email
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Cette adresse email est déjà utilisée.",
        )

    # Vérifier si le numéro de téléphone existe déjà
    existing_telephone = db.scalar(
        select(Utilisateur.id).where(
            Utilisateur.telephone == data.telephone
        )
    )

    if existing_telephone is not None:
        raise HTTPException(
            status_code=409,
            detail="Ce numéro de téléphone est déjà utilisé.",
        )

#--------------------------------------------------------------------------------------------

    user_data = data.model_dump(exclude={"password"})
    user_data["email"] = email
    user_data["password_hash"] = hash_password(data.password)

    if data.role == "superviseur" and user_data.get("formation_sanitaire_id") is None:
        raise HTTPException(
            status_code=422,
            detail="Un nouveau superviseur doit Ãªtre affectÃ© Ã  une formation sanitaire.",
        )

    user_data.update(
        normaliser_perimetre(db, data.role, user_data)
    )

    if data.role == "superviseur" and user_data.get("formation_sanitaire_id") is not None:
        deja_affecte = db.scalar(
            select(Utilisateur.id).where(
                Utilisateur.role == "superviseur",
                Utilisateur.actif.is_(True),
                Utilisateur.formation_sanitaire_id == user_data["formation_sanitaire_id"],
            )
        )
        if deja_affecte is not None:
            raise HTTPException(
                status_code=409,
                detail="Cette formation sanitaire possÃ¨de dÃ©jÃ  un superviseur actif.",
            )

    utilisateur = Utilisateur(**user_data)
    db.add(utilisateur)

    try:
        db.flush()
        if utilisateur.role == "superviseur" and utilisateur.formation_sanitaire_id is not None and utilisateur.actif:
            db.add(
                HistoriqueAffectationSuperviseur(
                    formation_sanitaire_id=utilisateur.formation_sanitaire_id,
                    ancien_superviseur_id=None,
                    nouveau_superviseur_id=utilisateur.id,
                    administrateur_id=current_user.id,
                    action="affectation_initiale",
                )
            )
        db.commit()
        db.refresh(utilisateur)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "CrÃ©ation impossible. VÃ©rifiez les identifiants "
                "des structures et les contraintes de la base."
            ),
        ) from None

    return utilisateur


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
) -> list[AdminUserResponse]:
    utilisateurs = db.scalars(
        select(Utilisateur)
        .order_by(Utilisateur.id)
        .offset(offset)
        .limit(limit)
    ).all()

    return list(utilisateurs)


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
) -> AdminUserResponse:
    utilisateur = db.get(Utilisateur, user_id)

    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    return utilisateur


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
) -> AdminUserResponse:
    utilisateur = db.get(Utilisateur, user_id)

    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    ancien_actif = utilisateur.actif
    ancien_role = utilisateur.role
    ancienne_formation_id = utilisateur.formation_sanitaire_id

    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="Aucune modification fournie.",
        )

    required_fields = {"nom", "prenom", "email", "fonction", "role", "actif"}
    for field in required_fields:
        if field in changes and changes[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"Le champ '{field}' ne peut pas Ãªtre nul.",
            )

    if user_id == current_user.id:
        if changes.get("actif") is False:
            raise HTTPException(
                status_code=400,
                detail="Vous ne pouvez pas dÃ©sactiver votre propre compte.",
            )
        if (
            "role" in changes
            and changes["role"] != current_user.role
        ):
            raise HTTPException(
                status_code=400,
                detail="Vous ne pouvez pas modifier votre propre rÃ´le.",
            )

    if "email" in changes and changes["email"] is not None:
        changes["email"] = changes["email"].strip().lower()
        existing = db.scalar(
            select(Utilisateur.id).where(
                Utilisateur.email == changes["email"],
                Utilisateur.id != user_id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Cette adresse email est dÃ©jÃ  utilisÃ©e.",
            )

    if "telephone" in changes:
        if changes["telephone"] is None:
            raise HTTPException(
                status_code=422,
                detail="Le numéro de téléphone ne peut pas être nul.",
            )

        existing_telephone = db.scalar(
            select(Utilisateur.id).where(
                Utilisateur.telephone == changes["telephone"],
                Utilisateur.id != user_id,
            )
        )
        if existing_telephone is not None:
            raise HTTPException(
                status_code=409,
                detail="Ce numéro de téléphone est déjà utilisé.",
            )

    if "password" in changes:
        password = changes.pop("password")
        if password is not None:
            changes["password_hash"] = hash_password(password)

#############################################################################################

    champs_scope = {
        "formation_sanitaire_id",
        "commune_id",
        "prefecture_id",
        "region_id",
    }

    role_final = changes.get("role", utilisateur.role)
    role_change = role_final != utilisateur.role

    if role_change and role_final == "superviseur":
        raise HTTPException(
            status_code=422,
            detail=(
                "Pour Ã©viter une affectation sans audit, crÃ©ez un compte de rÃ´le "
                "superviseur puis affectez-le Ã  la FS via la route dÃ©diÃ©e."
            ),
        )

    # Une affectation active ne doit pas disparaÃ®tre sans journal d'audit.
    # Il faut d'abord utiliser l'endpoint dÃ©diÃ© de retrait/remplacement.
    if (
        utilisateur.role == "superviseur"
        and utilisateur.formation_sanitaire_id is not None
        and (
            changes.get("actif") is False
            or role_final != "superviseur"
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Ce superviseur est affectÃ© Ã  une formation sanitaire. "
                "Retirez ou remplacez d'abord son affectation via l'endpoint dÃ©diÃ©."
            ),
        )

    # Une rÃ©activation d'un superviseur encore rattachÃ© Ã  une FS est possible
    # uniquement si aucun autre superviseur actif n'occupe dÃ©jÃ  cette FS.
    if (
        utilisateur.role == "superviseur"
        and changes.get("actif") is True
        and not utilisateur.actif
        and utilisateur.formation_sanitaire_id is not None
    ):
        autre_actif = db.scalar(
            select(Utilisateur.id).where(
                Utilisateur.id != utilisateur.id,
                Utilisateur.role == "superviseur",
                Utilisateur.actif.is_(True),
                Utilisateur.formation_sanitaire_id == utilisateur.formation_sanitaire_id,
            )
        )
        if autre_actif is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Un autre superviseur actif est dÃ©jÃ  affectÃ© Ã  cette FS. "
                    "Retirez ou remplacez cette affectation avant de rÃ©activer ce compte."
                ),
            )

    # Ne jamais transformer automatiquement le pÃ©rimÃ¨tre d'un agent
    # en pÃ©rimÃ¨tre de superviseur, ni rÃ©utiliser un ancien pÃ©rimÃ¨tre
    # lorsqu'un utilisateur change de rÃ´le.
    if role_change:
        scope_final = {champ: None for champ in champs_scope}
    else:
        scope_final = {
            "formation_sanitaire_id": utilisateur.formation_sanitaire_id,
            "commune_id": utilisateur.commune_id,
            "prefecture_id": utilisateur.prefecture_id,
            "region_id": utilisateur.region_id,
        }

    for champ in champs_scope:
        if champ in changes:
            scope_final[champ] = changes[champ]

    if (
        role_final == "superviseur"
        and scope_final["formation_sanitaire_id"] != utilisateur.formation_sanitaire_id
    ):
        raise HTTPException(
            status_code=422,
            detail="Utilisez la route d'affectation dÃ©diÃ©e pour affecter ou remplacer le superviseur d'une FS.",
        )

    if role_change and role_final == "superviseur" and scope_final["formation_sanitaire_id"] is None:
        raise HTTPException(
            status_code=422,
            detail="Un utilisateur qui devient superviseur doit Ãªtre affectÃ© Ã  une formation sanitaire.",
        )

    scope_normalise = normaliser_perimetre(
        db,
        role_final,
        scope_final,
    )

    for champ in champs_scope:
        changes.pop(champ, None)

    changes.update(scope_normalise)

    for field, value in changes.items():
        setattr(utilisateur, field, value)

#############################################################################################

    try:
        if (
            ancien_role == "superviseur"
            and ancien_actif is False
            and utilisateur.actif
            and utilisateur.formation_sanitaire_id is not None
            and utilisateur.formation_sanitaire_id == ancienne_formation_id
        ):
            db.add(
                HistoriqueAffectationSuperviseur(
                    formation_sanitaire_id=utilisateur.formation_sanitaire_id,
                    ancien_superviseur_id=None,
                    nouveau_superviseur_id=utilisateur.id,
                    administrateur_id=current_user.id,
                    action="reactivation",
                )
            )
        db.commit()
        db.refresh(utilisateur)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "Modification impossible. VÃ©rifiez les identifiants "
                "des structures et les contraintes de la base."
            ),
        ) from None

    return utilisateur

@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def supprimer_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
):
    utilisateur = db.scalar(
        select(Utilisateur)
        .where(Utilisateur.id == user_id)
        .with_for_update()
    )

    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if utilisateur.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas supprimer votre propre compte.",
        )

    if utilisateur.role == "administrateur_national":
        autres_admins = db.scalar(
            select(Utilisateur.id).where(
                Utilisateur.role == "administrateur_national",
                Utilisateur.actif.is_(True),
                Utilisateur.id != utilisateur.id,
            ).limit(1)
        )
        if autres_admins is None:
            raise HTTPException(
                status_code=409,
                detail="Impossible de supprimer le dernier administrateur national actif.",
            )

    if (
        utilisateur.role == "superviseur"
        and utilisateur.formation_sanitaire_id is not None
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Retirez d'abord l'affectation du superviseur via "
                "la route dÃ©diÃ©e avant de supprimer ce compte."
            ),
        )

    try:
        db.delete(utilisateur)
        db.commit()
        return {
            "message": "Utilisateur supprimÃ©.",
            "utilisateur_id": user_id,
        }
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Suppression impossible : cet utilisateur est rÃ©fÃ©rencÃ© "
                "par des fiches ou un historique. DÃ©sactivez son compte "
                "pour conserver les donnÃ©es sanitaires."
            ),
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="La suppression a Ã©chouÃ©.",
        ) from None

    
@router.patch("/users/{user_id}/desactiver", response_model=AdminUserResponse)
def desactiver_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
):
    utilisateur = db.scalar(
        select(Utilisateur)
        .where(Utilisateur.id == user_id)
        .with_for_update()
    )

    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if utilisateur.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas dÃ©sactiver votre propre compte.",
        )

    if not utilisateur.actif:
        raise HTTPException(status_code=409, detail="Ce compte est dÃ©jÃ  dÃ©sactivÃ©.")

    if utilisateur.role == "administrateur_national":
        autres_admins = db.scalar(
            select(Utilisateur.id).where(
                Utilisateur.role == "administrateur_national",
                Utilisateur.actif.is_(True),
                Utilisateur.id != utilisateur.id,
            ).limit(1)
        )
        if autres_admins is None:
            raise HTTPException(
                status_code=409,
                detail="Impossible de dÃ©sactiver le dernier administrateur national actif.",
            )

    # Un superviseur doit Ãªtre retirÃ© de sa FS par la route dÃ©diÃ©e.
    if (
        utilisateur.role == "superviseur"
        and utilisateur.formation_sanitaire_id is not None
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Retirez d'abord l'affectation du superviseur via "
                "DELETE /api/v1/admin/formations-sanitaires/{formation_id}/superviseur."
            ),
        )

    try:
        utilisateur.actif = False
        db.commit()
        db.refresh(utilisateur)
        return utilisateur
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="La dÃ©sactivation a Ã©chouÃ©.",
        ) from None

@router.put(
    "/formations-sanitaires/{formation_id}/superviseur",
    status_code=status.HTTP_200_OK,
)
def affecter_superviseur_fs(
    formation_id: int,
    data: AffectationSuperviseurFSRequest,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
):
    """Affecte ou remplace l'unique superviseur actif d'une FS."""
    try:
        formation = db.scalar(
            select(FormationSanitaire)
            .where(FormationSanitaire.id == formation_id)
            .with_for_update()
        )
        if formation is None or not formation.actif:
            raise HTTPException(
                status_code=404,
                detail="Formation sanitaire introuvable ou inactive.",
            )

        nouveau = db.scalar(
            select(Utilisateur)
            .where(Utilisateur.id == data.superviseur_id)
            .with_for_update()
        )
        if nouveau is None:
            raise HTTPException(status_code=404, detail="Superviseur introuvable.")
        if nouveau.role != "superviseur" or not nouveau.actif:
            raise HTTPException(
                status_code=422,
                detail="L'utilisateur choisi doit Ãªtre un superviseur actif.",
            )

        if (
            nouveau.formation_sanitaire_id is not None
            and nouveau.formation_sanitaire_id != formation_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Ce superviseur est dÃ©jÃ  affectÃ© Ã  une autre formation sanitaire.",
            )

        ancien = db.scalar(
            select(Utilisateur)
            .where(
                Utilisateur.role == "superviseur",
                Utilisateur.actif.is_(True),
                Utilisateur.formation_sanitaire_id == formation_id,
            )
            .with_for_update()
        )

        if ancien is not None and ancien.id == nouveau.id:
            return {
                "message": "Ce superviseur est dÃ©jÃ  affectÃ© Ã  cette formation sanitaire.",
                "formation_sanitaire_id": formation_id,
                "superviseur_id": nouveau.id,
            }

        if ancien is not None:
            ancien.formation_sanitaire_id = None

        # Un superviseur FS n'a pas de pÃ©rimÃ¨tre territorial concurrent.
        nouveau.formation_sanitaire_id = formation_id
        nouveau.commune_id = None
        nouveau.prefecture_id = None
        nouveau.region_id = None

        db.add(
            HistoriqueAffectationSuperviseur(
                formation_sanitaire_id=formation_id,
                ancien_superviseur_id=ancien.id if ancien else None,
                nouveau_superviseur_id=nouveau.id,
                administrateur_id=current_user.id,
                action="remplacement" if ancien else "affectation",
            )
        )
        db.commit()
        db.refresh(nouveau)
        return {
            "message": "Le superviseur de la formation sanitaire a Ã©tÃ© enregistrÃ©.",
            "formation_sanitaire_id": formation_id,
            "ancien_superviseur_id": ancien.id if ancien else None,
            "superviseur_id": nouveau.id,
        }
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflit d'affectation : cette FS possÃ¨de dÃ©jÃ  un superviseur actif ou ce compte est affectÃ© ailleurs.",
        ) from None
    except Exception:
        db.rollback()
        raise


@router.delete(
    "/formations-sanitaires/{formation_id}/superviseur",
    status_code=status.HTTP_200_OK,
)
def retirer_superviseur_fs(
    formation_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
):
    """Retire explicitement le superviseur actif d'une FS, avec audit."""
    try:
        formation = db.scalar(
            select(FormationSanitaire)
            .where(FormationSanitaire.id == formation_id)
            .with_for_update()
        )
        if formation is None:
            raise HTTPException(status_code=404, detail="Formation sanitaire introuvable.")

        ancien = db.scalar(
            select(Utilisateur)
            .where(
                Utilisateur.role == "superviseur",
                Utilisateur.actif.is_(True),
                Utilisateur.formation_sanitaire_id == formation_id,
            )
            .with_for_update()
        )
        if ancien is None:
            raise HTTPException(
                status_code=404,
                detail="Aucun superviseur actif n'est affectÃ© Ã  cette formation sanitaire.",
            )

        ancien.formation_sanitaire_id = None
        db.add(
            HistoriqueAffectationSuperviseur(
                formation_sanitaire_id=formation_id,
                ancien_superviseur_id=ancien.id,
                nouveau_superviseur_id=None,
                administrateur_id=current_user.id,
                action="retrait",
            )
        )
        db.commit()
        return {
            "message": "L'affectation du superviseur a Ã©tÃ© retirÃ©e.",
            "formation_sanitaire_id": formation_id,
            "ancien_superviseur_id": ancien.id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "/users/permuter-affectations",
    response_model=PermutationAffectationsResponse,
    status_code=status.HTTP_200_OK,
)
def permuter_affectations(
    data: PermutationAffectationsRequest,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_only),
):
    """Permute les affectations FS de deux agents et journalise l'opÃ©ration."""

    if data.agent_a_id == data.agent_b_id:
        raise HTTPException(
            status_code=422,
            detail="Les deux identifiants doivent Ãªtre diffÃ©rents.",
        )

    try:
        # Verrouiller les deux comptes dans un ordre stable.
        agents = db.scalars(
            select(Utilisateur)
            .where(
                Utilisateur.id.in_([data.agent_a_id, data.agent_b_id])
            )
            .order_by(Utilisateur.id)
            .with_for_update()
        ).all()

        agents_par_id = {agent.id: agent for agent in agents}
        agent_a = agents_par_id.get(data.agent_a_id)
        agent_b = agents_par_id.get(data.agent_b_id)

        if agent_a is None or agent_b is None:
            raise HTTPException(
                status_code=404,
                detail="Un ou les deux agents sont introuvables.",
            )

        for agent in (agent_a, agent_b):
            if agent.role != "agent_fs":
                raise HTTPException(
                    status_code=422,
                    detail="Les deux utilisateurs doivent avoir le rÃ´le agent_fs.",
                )
            if agent.formation_sanitaire_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Chaque agent doit avoir une formation sanitaire affectÃ©e.",
                )

        ancienne_fs_a_id = agent_a.formation_sanitaire_id
        ancienne_fs_b_id = agent_b.formation_sanitaire_id

        if ancienne_fs_a_id == ancienne_fs_b_id:
            raise HTTPException(
                status_code=409,
                detail="Les deux agents sont dÃ©jÃ  affectÃ©s Ã  la mÃªme formation sanitaire.",
            )

        # Verrouiller les deux formations sanitaires et vÃ©rifier leur Ã©tat.
        formations = db.scalars(
            select(FormationSanitaire)
            .where(
                FormationSanitaire.id.in_(
                    [ancienne_fs_a_id, ancienne_fs_b_id]
                )
            )
            .order_by(FormationSanitaire.id)
            .with_for_update()
        ).all()

        formations_par_id = {fs.id: fs for fs in formations}

        if len(formations_par_id) != 2:
            raise HTTPException(
                status_code=409,
                detail="Une des formations sanitaires n'existe plus.",
            )

        if any(not fs.actif for fs in formations):
            raise HTTPException(
                status_code=409,
                detail="Les deux formations sanitaires doivent Ãªtre actives.",
            )

        # Recalculer les pÃ©rimÃ¨tres complets Ã  partir de la nouvelle FS.
        scope_a = normaliser_perimetre(
            db,
            "agent_fs",
            {"formation_sanitaire_id": ancienne_fs_b_id},
        )
        scope_b = normaliser_perimetre(
            db,
            "agent_fs",
            {"formation_sanitaire_id": ancienne_fs_a_id},
        )

        for champ, valeur in scope_a.items():
            setattr(agent_a, champ, valeur)

        for champ, valeur in scope_b.items():
            setattr(agent_b, champ, valeur)

        historique = HistoriquePermutationAffectation(
            agent_a_id=agent_a.id,
            agent_b_id=agent_b.id,
            administrateur_id=current_user.id,
            ancienne_fs_a_id=ancienne_fs_a_id,
            nouvelle_fs_a_id=ancienne_fs_b_id,
            ancienne_fs_b_id=ancienne_fs_b_id,
            nouvelle_fs_b_id=ancienne_fs_a_id,
        )
        db.add(historique)
        db.flush()

        db.commit()
        db.refresh(agent_a)
        db.refresh(agent_b)

        return PermutationAffectationsResponse(
            message="Les affectations des deux agents ont Ã©tÃ© permutÃ©es.",
            agent_a=agent_a,
            agent_b=agent_b,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="La permutation a Ã©chouÃ©. Aucune modification n'a Ã©tÃ© conservÃ©e.",
        ) from None

