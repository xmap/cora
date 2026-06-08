"""MCP tool for the `register_clearance` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.

The discriminated-union shapes (HazardClassification, ClearanceBinding)
are accepted as `kind`-tagged Pydantic models, mirroring the REST
route's wire shape exactly.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.safety.aggregates.clearance import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
    CLEARANCE_HAZARD_NOTES_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    AssetBinding,
    ClearanceBinding,
    ClearanceKind,
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
    SCHEME_CODE_CODE_MAX_LENGTH,
    SCHEME_CODE_SCHEME_MAX_LENGTH,
    SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH,
    GHSPictogram,
    HazardClassification,
    NFPA704Rating,
    RiskBand,
    SchemeCode,
)
from cora.safety.features.register_clearance.command import RegisterClearance
from cora.safety.features.register_clearance.handler import IdempotentHandler
from cora.shared.identifier import (
    IDENTIFIER_SCHEME_MAX_LENGTH,
    IDENTIFIER_VALUE_MAX_LENGTH,
    Identifier,
)


class _BindingSubjectArg(BaseModel):
    kind: Literal["Subject"]
    id: UUID


class _BindingAssetArg(BaseModel):
    kind: Literal["Asset"]
    id: UUID


class _BindingRunArg(BaseModel):
    kind: Literal["Run"]
    id: UUID


class _BindingProcedureArg(BaseModel):
    kind: Literal["Procedure"]
    id: UUID


class _BindingExternalArg(BaseModel):
    kind: Literal["External"]
    scheme: str = Field(..., min_length=1, max_length=IDENTIFIER_SCHEME_MAX_LENGTH)
    value: str = Field(..., min_length=1, max_length=IDENTIFIER_VALUE_MAX_LENGTH)


_BindingArg = Annotated[
    _BindingSubjectArg
    | _BindingAssetArg
    | _BindingRunArg
    | _BindingProcedureArg
    | _BindingExternalArg,
    Field(discriminator="kind"),
]


class _NFPA704Arg(BaseModel):
    kind: Literal["NFPA704"]
    health: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    flammability: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    instability: int = Field(..., ge=NFPA704_MIN_RATING, le=NFPA704_MAX_RATING)
    special: str | None = None


class _RiskBandArg(BaseModel):
    kind: Literal["RiskBand"]
    band: RiskBand


class _GHSArg(BaseModel):
    kind: Literal["GHS"]
    code: str = Field(..., description=f"GHS code; one of {sorted(GHS_VALID_PICTOGRAMS)}.")
    statement_codes: list[str] = Field(default_factory=list)


class _SchemeArg(BaseModel):
    kind: Literal["Scheme"]
    scheme: str = Field(..., min_length=1, max_length=SCHEME_CODE_SCHEME_MAX_LENGTH)
    code: str = Field(..., min_length=1, max_length=SCHEME_CODE_CODE_MAX_LENGTH)
    severity_label: str = Field(default="", max_length=SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH)


_ClassificationArg = Annotated[
    _NFPA704Arg | _RiskBandArg | _GHSArg | _SchemeArg,
    Field(discriminator="kind"),
]


class _HazardDeclarationArg(BaseModel):
    target: _BindingArg
    classifications: list[_ClassificationArg] = Field(default_factory=list[_ClassificationArg])
    mitigations: list[str] = Field(default_factory=list[str])
    notes: str | None = Field(default=None, max_length=CLEARANCE_HAZARD_NOTES_MAX_LENGTH)


class RegisterClearanceOutput(BaseModel):
    """Structured output of the `register_clearance` MCP tool."""

    clearance_id: UUID


def _binding_from_arg(arg: _BindingArg) -> ClearanceBinding:
    if isinstance(arg, _BindingSubjectArg):
        return SubjectBinding(subject_id=arg.id)
    if isinstance(arg, _BindingAssetArg):
        return AssetBinding(asset_id=arg.id)
    if isinstance(arg, _BindingRunArg):
        return RunBinding(run_id=arg.id)
    if isinstance(arg, _BindingProcedureArg):
        return ProcedureBinding(procedure_id=arg.id)
    return ExternalRefBinding(ref=Identifier(scheme=arg.scheme, value=arg.value))


def _classification_from_arg(arg: _ClassificationArg) -> HazardClassification:
    if isinstance(arg, _NFPA704Arg):
        return NFPA704Rating(
            health=arg.health,
            flammability=arg.flammability,
            instability=arg.instability,
            special=arg.special,
        )
    if isinstance(arg, _RiskBandArg):
        return arg.band
    if isinstance(arg, _GHSArg):
        return GHSPictogram(
            code=arg.code,
            statement_codes=frozenset(arg.statement_codes),
        )
    return SchemeCode(
        scheme=arg.scheme,
        code=arg.code,
        severity_label=arg.severity_label,
    )


def _declaration_from_arg(arg: _HazardDeclarationArg) -> HazardDeclaration:
    return HazardDeclaration(
        target=_binding_from_arg(arg.target),
        classifications=frozenset(_classification_from_arg(c) for c in arg.classifications),
        mitigations=frozenset(arg.mitigations),
        notes=arg.notes,
    )


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_clearance` tool on the given MCP server."""

    @mcp.tool(
        name="register_clearance",
        description=(
            "Register a new safety-form clearance (APS ESAF, NSLS-II SAF, "
            "ESRF A-form/SAF, MAX IV DUO/ESRA, DLS ERA/PLHD, DESY DOOR, "
            "ALS ESAF, SLAC BTR, SPring-8 Form 9). Lands in 'Defined' "
            "status; transitions through Submitted -> UnderReview -> "
            "Approved -> Active via subsequent slices."
        ),
    )
    async def register_clearance_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        kind: Annotated[
            ClearanceKind,
            Field(description="Form-type (10 facility-independent form-types)."),
        ],
        facility_asset_id: Annotated[
            UUID,
            Field(
                description=(
                    "Reference to the Asset.Level.Site for the facility that issued "
                    "(or will issue) this clearance."
                ),
            ),
        ],
        title: Annotated[
            str,
            Field(
                min_length=1,
                max_length=CLEARANCE_TITLE_MAX_LENGTH,
                description="Operator-readable title.",
            ),
        ],
        bindings: Annotated[
            list[_BindingArg],
            Field(
                min_length=1,
                description=(
                    "Multi-binding: what this clearance gates (Subject / Asset / "
                    "Run / Procedure / External)."
                ),
            ),
        ],
        declarations: Annotated[
            list[_HazardDeclarationArg] | None,
            Field(
                description=("Hazard claims per binding target. None / empty list allowed."),
            ),
        ] = None,
        risk_band: Annotated[
            RiskBand | None,
            Field(default=None, description="Optional Green/Yellow/Red triage band."),
        ] = None,
        external_id: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
                description="Optional facility-minted ID (for example 'ESAF-12345').",
            ),
        ] = None,
        valid_from: Annotated[
            datetime | None,
            Field(default=None, description="Effective-from timestamp; ISO-8601 on the wire."),
        ] = None,
        valid_until: Annotated[
            datetime | None,
            Field(
                default=None,
                description=(
                    "Effective-until timestamp; ISO-8601 on the wire. Must be strictly "
                    "greater than `valid_from` (zero-duration windows rejected at decider)."
                ),
            ),
        ] = None,
    ) -> RegisterClearanceOutput:
        handler = get_handler()
        clearance_id = await handler(
            RegisterClearance(
                kind=kind,
                facility_asset_id=facility_asset_id,
                title=title,
                bindings=frozenset(_binding_from_arg(b) for b in bindings),
                declarations=frozenset(_declaration_from_arg(d) for d in (declarations or [])),
                risk_band=risk_band,
                external_id=external_id,
                valid_from=valid_from,
                valid_until=valid_until,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterClearanceOutput(clearance_id=clearance_id)
