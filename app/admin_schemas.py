
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
import re
from pydantic import field_validator

UserRole = Literal[
    "agent_fs",
    "superviseur",
    "administrateur_national",
]


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nom: str = Field(min_length=1, max_length=150)
    prenom: str = Field(min_length=1, max_length=150)
    email: str = Field(
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    telephone: str = Field(min_length=8, max_length=20)

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, valeur: str) -> str:
        telephone = re.sub(r"[\s().-]", "", valeur)

        if not re.fullmatch(r"\+?[0-9]{8,15}", telephone):
            raise ValueError("Le numÃ©ro de tÃ©lÃ©phone est invalide.")

        return telephone
    password: str = Field(min_length=12, max_length=128)
    fonction: str = Field(min_length=1, max_length=150)
    role: UserRole

    formation_sanitaire_id: int | None = Field(default=None, gt=0)
    commune_id: int | None = Field(default=None, gt=0)
    prefecture_id: int | None = Field(default=None, gt=0)
    region_id: int | None = Field(default=None, gt=0)

    actif: bool = True


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nom: str | None = Field(default=None, min_length=1, max_length=150)
    prenom: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(
        default=None,
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    telephone: str | None = Field(
        default=None,
        min_length=8,
        max_length=20,
    )

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None

        telephone = re.sub(r"[\s().-]", "", valeur)

        if not re.fullmatch(r"\+?[0-9]{8,15}", telephone):
            raise ValueError("Le numÃ©ro de tÃ©lÃ©phone est invalide.")

        return telephone
    password: str | None = Field(default=None, min_length=12, max_length=128)
    fonction: str | None = Field(default=None, min_length=1, max_length=150)
    role: UserRole | None = None

    formation_sanitaire_id: int | None = Field(default=None, gt=0)
    commune_id: int | None = Field(default=None, gt=0)
    prefecture_id: int | None = Field(default=None, gt=0)
    region_id: int | None = Field(default=None, gt=0)

    actif: bool | None = None


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str
    email: str
    telephone: str | None
    fonction: str
    role: str

    formation_sanitaire_id: int | None
    commune_id: int | None
    prefecture_id: int | None
    region_id: int | None

    actif: bool
    cree_le: object


class PermutationAffectationsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_a_id: int = Field(gt=0)
    agent_b_id: int = Field(gt=0)


class PermutationAffectationsResponse(BaseModel):
    message: str
    agent_a: AdminUserResponse
    agent_b: AdminUserResponse


class AffectationSuperviseurFSRequest(BaseModel):
    """Affecte un superviseur actif Ã  une formation sanitaire."""
    model_config = ConfigDict(extra="forbid")

    superviseur_id: int = Field(gt=0)

