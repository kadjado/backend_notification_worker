from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FichePaludismeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    formation_sanitaire_id: int = Field(gt=0)
    date_consultation: date
    num_oc: str = Field(min_length=1, max_length=50)
    mois: int = Field(ge=1, le=12)
    age: int = Field(ge=0, le=120)
    sexe: Literal["M", "F"]

    grossesse: str | None = Field(default=None, max_length=20)
    tpi1: bool
    tpi2: str = Field(max_length=20)

    type_consultation: Literal[
        "Nouveau cas",
        "Reconsultation",
        "Référé",
    ]
    fievre: bool
    motif_consultation: str | None = Field(default=None, max_length=255)

    ge_realisee: bool
    type_ge: str | None = Field(default=None, max_length=30)
    charge_sigep: str | None = Field(default=None, max_length=50)
    tdr_realise: bool
    type_tdr_id: int | None = Field(default=None, gt=0)
    resultat_tdr: str | None = Field(default=None, max_length=20)
    numero_laboratoire: str | None = Field(default=None, max_length=50)

    diagnostic: Literal[
        "Paludisme simple",
        "Paludisme grave",
        "Non confirmé",
        "Autre",
    ]

    asaq: bool
    arlm: bool
    quinine_comprime: bool
    quinine_injectable: bool
    artesunate_injectable: bool
    autre_traitement: str | None = Field(default=None, max_length=255)

    hospitalise: bool
    date_sortie: date | None = None
    issue_hospitalisation: Literal[
        "Guéri",
        "Transféré",
        "Décédé",
        "Sorti contre avis",
        "En cours",
    ] | None = None

    
    @model_validator(mode="after")
    def verifier_coherence(self):
        if self.mois != self.date_consultation.month:
            raise ValueError(
                "Le mois doit correspondre au mois de la date de consultation."
            )

        if self.date_consultation > date.today():
            raise ValueError(
                "La date de consultation ne peut pas être dans le futur."
            )

        if (
            self.date_sortie is not None
            and self.date_sortie < self.date_consultation
        ):
            raise ValueError(
                "La date de sortie ne peut pas précéder la consultation."
            )

        if not self.hospitalise:
            if self.date_sortie is not None:
                raise ValueError(
                    "La date de sortie doit être vide si le patient n'est pas hospitalisé."
                )

            if self.issue_hospitalisation is not None:
                raise ValueError(
                    "L'issue d'hospitalisation doit être vide si le patient n'est pas hospitalisé."
                )

        return self


class FichePaludismeResponse(FichePaludismeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero_fiche: str
    agent_id: int
    date_saisie: datetime
    fonction_agent: str
    validation_confirmee: bool
    validee_par_id: int | None
    validee_le: datetime | None
    version: int
    cree_le: datetime
    modifie_le: datetime
    supprime_le: datetime | None


class FichePaludismeUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    date_consultation: date | None = None
    num_oc: str | None = Field(default=None, min_length=1, max_length=50)
    mois: int | None = Field(default=None, ge=1, le=12)
    age: int | None = Field(default=None, ge=0, le=120)
    sexe: Literal["M", "F"] | None = None
    grossesse: str | None = Field(default=None, max_length=20)
    tpi1: bool | None = None
    tpi2: str | None = Field(default=None, max_length=20)
    type_consultation: Literal[
        "Nouveau cas", "Reconsultation", "Référé"
    ] | None = None
    fievre: bool | None = None
    motif_consultation: str | None = Field(default=None, max_length=255)
    ge_realisee: bool | None = None
    type_ge: str | None = Field(default=None, max_length=30)
    charge_sigep: str | None = Field(default=None, max_length=50)
    tdr_realise: bool | None = None
    type_tdr_id: int | None = Field(default=None, gt=0)
    resultat_tdr: str | None = Field(default=None, max_length=20)
    numero_laboratoire: str | None = Field(default=None, max_length=50)
    diagnostic: Literal[
        "Paludisme simple", "Paludisme grave", "Non confirmé", "Autre"
    ] | None = None
    asaq: bool | None = None
    arlm: bool | None = None
    quinine_comprime: bool | None = None
    quinine_injectable: bool | None = None
    artesunate_injectable: bool | None = None
    autre_traitement: str | None = Field(default=None, max_length=255)
    hospitalise: bool | None = None
    date_sortie: date | None = None
    issue_hospitalisation: Literal[
        "Guéri", "Transféré", "Décédé", "Sorti contre avis", "En cours"
    ] | None = None

    @model_validator(mode="after")
    def verifier_coherence_partielle(self):
        valeurs = self.model_dump(exclude_unset=True)

        if not valeurs:
            raise ValueError("Au moins un champ doit être fourni.")

        if valeurs.get("mois") is not None and valeurs.get("date_consultation") is not None:
            if valeurs["mois"] != valeurs["date_consultation"].month:
                raise ValueError(
                    "Le mois doit correspondre au mois de la date de consultation."
                )

        return self
