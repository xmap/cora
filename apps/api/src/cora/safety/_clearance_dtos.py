"""Shared Pydantic discriminated-union DTOs for the Clearance wire shape.

BC-level scaffolding consumed by every slice that builds a Clearance
from JSON request bodies / MCP tool args: today `register_clearance`
(creates a new clearance) and `amend_clearance` (creates the child of
an amendment). Hoisted to the BC level so the slices don't reach
across each other (the cross-slice-independence architecture
fitness function would otherwise reject the import).

Naming: leading underscore on the filename marks this as BC-private
(not part of the public API surface); the contained class + function
names are public-within-the-BC so importing slices reference them
without the underscore (`BindingDTO`, `binding_from_dto`, etc.).

Layout:
  - Five `Binding<X>DTO` classes + the union `BindingDTO`
  - Four `<X>DTO` classification classes + the union `ClassificationDTO`
  - `HazardDeclarationDTO`
  - `binding_from_dto` / `classification_from_dto` / `declaration_from_dto`
    DTO->domain converters

Same shape as the typed-domain VOs in
`cora.safety.aggregates.clearance.*`; the converters bridge the
Pydantic-wire side to the frozen-dataclass domain side.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cora.safety.aggregates.clearance import (
    CLEARANCE_HAZARD_NOTES_MAX_LENGTH,
    AssetBinding,
    ClearanceBinding,
    ExternalRefBinding,
    HazardDeclaration,
    ProcedureBinding,
    RunBinding,
    SubjectBinding,
)
from cora.safety.aggregates.clearance.hazard_classification import (
    GHS_VALID_PICTOGRAMS,
    NFPA704_MAX_RATING,
    NFPA704_MIN_RATING,
    NFPA704_VALID_SPECIAL,
    SCHEME_CODE_CODE_MAX_LENGTH,
    SCHEME_CODE_SCHEME_MAX_LENGTH,
    SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH,
    GHSPictogram,
    HazardClassification,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)
from cora.shared.identifier import (
    IDENTIFIER_SCHEME_MAX_LENGTH,
    IDENTIFIER_VALUE_MAX_LENGTH,
    Identifier,
)

# ---------------------------------------------------------------------------
# Binding discriminated-union DTOs
# ---------------------------------------------------------------------------


class BindingSubjectDTO(BaseModel):
    kind: Literal["Subject"]
    id: UUID = Field(..., description="Target Subject's id.")


class BindingAssetDTO(BaseModel):
    kind: Literal["Asset"]
    id: UUID = Field(..., description="Target Asset's id.")


class BindingRunDTO(BaseModel):
    kind: Literal["Run"]
    id: UUID = Field(..., description="Target Run's id.")


class BindingProcedureDTO(BaseModel):
    kind: Literal["Procedure"]
    id: UUID = Field(..., description="Target Procedure's id.")


class BindingExternalDTO(BaseModel):
    kind: Literal["External"]
    scheme: str = Field(
        ...,
        min_length=1,
        max_length=IDENTIFIER_SCHEME_MAX_LENGTH,
        description=(
            "External-ref scheme: 'proposal' | 'btr' | 'lab_visit' | 'session' "
            "| <future>. Anti-corruption pattern for upstream-deferred concepts "
            "CORA does NOT model (per BC map line 111)."
        ),
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=IDENTIFIER_VALUE_MAX_LENGTH,
        description="Facility-minted external ID (for example 'GUP-12345').",
    )


BindingDTO = Annotated[
    BindingSubjectDTO | BindingAssetDTO | BindingRunDTO | BindingProcedureDTO | BindingExternalDTO,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Classification discriminated-union DTOs
# ---------------------------------------------------------------------------


class NFPA704DTO(BaseModel):
    kind: Literal["NFPA704"]
    health: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    flammability: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    instability: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    special: str | None = Field(
        default=None,
        description=(f"Optional NFPA 704 'special' code: one of {sorted(NFPA704_VALID_SPECIAL)}."),
    )


class RiskBandDTO(BaseModel):
    kind: Literal["RiskBand"]
    band: RiskBand


class GhsDto(BaseModel):
    kind: Literal["GHS"]
    code: str = Field(
        ...,
        description=f"GHS pictogram code; one of {sorted(GHS_VALID_PICTOGRAMS)}.",
    )
    statement_codes: list[str] = Field(
        default_factory=list,
        description="GHS H-statement codes triggering this pictogram (for example 'H300').",
    )


class SchemeDTO(BaseModel):
    kind: Literal["Scheme"]
    scheme: str = Field(..., min_length=1, max_length=SCHEME_CODE_SCHEME_MAX_LENGTH)
    code: str = Field(..., min_length=1, max_length=SCHEME_CODE_CODE_MAX_LENGTH)
    severity_label: str = Field(
        default="",
        max_length=SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH,
    )


ClassificationDTO = Annotated[
    NFPA704DTO | RiskBandDTO | GhsDto | SchemeDTO,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# HazardDeclaration DTO
# ---------------------------------------------------------------------------


class HazardDeclarationDTO(BaseModel):
    target: BindingDTO
    classifications: list[ClassificationDTO] = Field(default_factory=list[ClassificationDTO])
    mitigations: list[str] = Field(
        default_factory=list[str],
        description=("Free-form mitigation refs: PPE codes, training cert refs, procedure IDs."),
    )
    notes: str | None = Field(
        default=None,
        max_length=CLEARANCE_HAZARD_NOTES_MAX_LENGTH,
    )


# ---------------------------------------------------------------------------
# DTO -> domain converters
# ---------------------------------------------------------------------------


def binding_from_dto(dto: BindingDTO) -> ClearanceBinding:
    if isinstance(dto, BindingSubjectDTO):
        return SubjectBinding(subject_id=dto.id)
    if isinstance(dto, BindingAssetDTO):
        return AssetBinding(asset_id=dto.id)
    if isinstance(dto, BindingRunDTO):
        return RunBinding(run_id=dto.id)
    if isinstance(dto, BindingProcedureDTO):
        return ProcedureBinding(procedure_id=dto.id)
    return ExternalRefBinding(ref=Identifier(scheme=dto.scheme, value=dto.value))


def classification_from_dto(dto: ClassificationDTO) -> HazardClassification:
    if isinstance(dto, NFPA704DTO):
        return NFPA704Rating(
            health=dto.health,
            flammability=dto.flammability,
            instability=dto.instability,
            special=dto.special,
        )
    if isinstance(dto, RiskBandDTO):
        return dto.band
    if isinstance(dto, GhsDto):
        return GHSPictogram(
            code=dto.code,
            statement_codes=frozenset(dto.statement_codes),
        )
    return SchemeCode(
        scheme=dto.scheme,
        code=dto.code,
        severity_label=dto.severity_label,
    )


def declaration_from_dto(dto: HazardDeclarationDTO) -> HazardDeclaration:
    return HazardDeclaration(
        target=binding_from_dto(dto.target),
        classifications=frozenset(classification_from_dto(c) for c in dto.classifications),
        mitigations=frozenset(dto.mitigations),
        notes=dto.notes,
    )


__all__ = [
    "NFPA704DTO",
    "BindingAssetDTO",
    "BindingDTO",
    "BindingExternalDTO",
    "BindingProcedureDTO",
    "BindingRunDTO",
    "BindingSubjectDTO",
    "ClassificationDTO",
    "GhsDto",
    "HazardDeclarationDTO",
    "RiskBandDTO",
    "SchemeDTO",
    "binding_from_dto",
    "classification_from_dto",
    "declaration_from_dto",
]
