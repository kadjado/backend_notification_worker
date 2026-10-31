
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StructureBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=50)
    libelle: str = Field(min_length=1, max_length=200)


class RegionCreate(StructureBase):
    code: str = Field(min_length=1, max_length=30)
    libelle: str = Field(min_length=1, max_length=150)


class RegionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=30)
    libelle: str | None = Field(default=None, min_length=1, max_length=150)


class RegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    libelle: str


class PrefectureCreate(StructureBase):
    code: str = Field(min_length=1, max_length=30)
    libelle: str = Field(min_length=1, max_length=150)
    region_id: int = Field(gt=0)


class PrefectureUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=30)
    libelle: str | None = Field(default=None, min_length=1, max_length=150)
    region_id: int | None = Field(default=None, gt=0)


class PrefectureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    libelle: str
    region_id: int


class CommuneCreate(StructureBase):
    code: str = Field(min_length=1, max_length=30)
    libelle: str = Field(min_length=1, max_length=150)
    prefecture_id: int = Field(gt=0)


class CommuneUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=30)
    libelle: str | None = Field(default=None, min_length=1, max_length=150)
    prefecture_id: int | None = Field(default=None, gt=0)


class CommuneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    libelle: str
    prefecture_id: int


class FormationSanitaireCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=50)
    libelle: str = Field(min_length=1, max_length=200)
    type_fs: Literal["USP", "CMS", "Hôpital"]
    commune_id: int = Field(gt=0)
    actif: bool = True


class FormationSanitaireUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=50)
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    type_fs: Literal["USP", "CMS", "Hôpital"] | None = None
    commune_id: int | None = Field(default=None, gt=0)
    actif: bool | None = None


class FormationSanitaireResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    libelle: str
    type_fs: str
    commune_id: int
    actif: bool
