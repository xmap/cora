"""HTTP route for the `update_asset_partition_rule` slice.

Action endpoint at `POST /assets/{asset_id}/partition-rule`. Body
carries `partition_rule`: a Pydantic discriminated-union model for
the PartitionRule typed VO, or null to clear the rule. 200 OK on
success with an empty response body.

PartitionRule is a frozen-dataclass discriminated union at the domain
layer (Affine, Aggregation, LookupTable, CompositePartition,
SolverReference). Pydantic models exist only here at the route
boundary for JSON body parsing; the route converts to the frozen-
dataclass union before invoking the handler.

Uses HTTP POST (idempotency=none; mutation, not genesis) targeting a
sub-resource that already exists. The POST semantics match the
domain intent (update or clear the rule).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    AggregatorKind,
    CompositePartition,
    ExtrapolationKind,
    InterpolationKind,
    InvalidPartitionRuleError,
    LookupTable,
    PartitionKind,
    PartitionRule,
    PartitionRuleKind,
    ReadbackAggregatorKind,
    SolverReference,
    SolverTransportKind,
)
from cora.equipment.features.update_asset_partition_rule.command import (
    UpdateAssetPartitionRule,
)
from cora.equipment.features.update_asset_partition_rule.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AffineBody(BaseModel):
    """Pydantic model for Affine partition rule."""

    kind: Literal[PartitionRuleKind.AFFINE] = PartitionRuleKind.AFFINE
    gain: float = 1.0
    offset: float = 0.0
    unit_in: str = ""
    unit_out: str = ""


class AggregationBody(BaseModel):
    """Pydantic model for Aggregation partition rule."""

    kind: Literal[PartitionRuleKind.AGGREGATION] = PartitionRuleKind.AGGREGATION
    aggregator_kind: AggregatorKind = AggregatorKind.SUM
    constituent_count: int = 1


class LookupTableBody(BaseModel):
    """Pydantic model for LookupTable partition rule."""

    kind: Literal[PartitionRuleKind.LOOKUP_TABLE] = PartitionRuleKind.LOOKUP_TABLE
    calibration_id: UUID
    calibration_revision_id: UUID
    interpolation_kind: InterpolationKind = InterpolationKind.LINEAR
    extrapolation_kind: ExtrapolationKind = ExtrapolationKind.CLAMP
    invertible: bool = True
    readback_aggregator_kind: ReadbackAggregatorKind | None = None
    unit_in: str = ""
    unit_out: str = ""


class CompositePartitionBody(BaseModel):
    """Pydantic model for CompositePartition rule."""

    kind: Literal[PartitionRuleKind.COMPOSITE_PARTITION] = PartitionRuleKind.COMPOSITE_PARTITION
    partition_kind: PartitionKind = PartitionKind.PROPORTIONAL_FILL
    constituent_count: int = 2
    # Pydantic v2 coerces inbound JSON arrays of 2-element arrays into
    # list[tuple[str, float]] natively; no manual field_validator needed.
    partition_parameters: list[tuple[str, float]] = Field(default_factory=list[tuple[str, float]])
    readback_aggregator_kind: ReadbackAggregatorKind = ReadbackAggregatorKind.SUM


class SolverReferenceBody(BaseModel):
    """Pydantic model for SolverReference partition rule."""

    kind: Literal[PartitionRuleKind.SOLVER_REFERENCE] = PartitionRuleKind.SOLVER_REFERENCE
    solver_id: str
    solver_version: str
    solver_transport_kind: SolverTransportKind = SolverTransportKind.SOFT_IOC_RECORD
    residual_tolerance_limit: float = 0.0
    singularity_threshold: float = 0.0
    invertible: bool = True
    readback_aggregator_kind: ReadbackAggregatorKind | None = None


# Discriminated union of all PartitionRule Pydantic shapes
PartitionRuleBody = Annotated[
    AffineBody | AggregationBody | LookupTableBody | CompositePartitionBody | SolverReferenceBody,
    Field(discriminator="kind"),
]


class UpdateAssetPartitionRuleRequest(BaseModel):
    """Body for `POST /assets/{asset_id}/partition-rule`.

    `partition_rule` is a discriminated-union Pydantic model covering
    the 5 PartitionRule shapes (Affine, Aggregation, LookupTable,
    CompositePartition, SolverReference), or null to clear the rule.

    The route converts the Pydantic model to the frozen-dataclass union
    before invoking the handler. Pydantic 422 fires on shape mismatch
    (unknown kind, missing required field for kind, etc.).
    """

    partition_rule: PartitionRuleBody | None = Field(
        default=None,
        description=(
            "Partition rule as a discriminated union (kind + shape-specific fields), "
            "or null to clear the rule. Unknown kind or missing required fields "
            "for the kind trigger HTTP 422."
        ),
    )


def _to_partition_rule(body: PartitionRuleBody | None) -> PartitionRule | None:
    """Convert a Pydantic body shape to the frozen-dataclass union.

    Dispatches on body.kind and constructs the matching frozen dataclass
    from cora.equipment.aggregates._partition_rule. If body is None,
    returns None (clear). Re-runs each shape's __post_init__ validators
    so shape construction failures surface here with InvalidPartitionRuleError.
    """
    if body is None:
        return None

    match body:
        case AffineBody(
            gain=gain,
            offset=offset,
            unit_in=unit_in,
            unit_out=unit_out,
        ):
            return Affine(
                gain=gain,
                offset=offset,
                unit_in=unit_in,
                unit_out=unit_out,
            )
        case AggregationBody(
            aggregator_kind=aggregator_kind,
            constituent_count=constituent_count,
        ):
            return Aggregation(
                aggregator_kind=aggregator_kind,
                constituent_count=constituent_count,
            )
        case LookupTableBody(
            calibration_id=calibration_id,
            calibration_revision_id=calibration_revision_id,
            interpolation_kind=interpolation_kind,
            extrapolation_kind=extrapolation_kind,
            invertible=invertible,
            readback_aggregator_kind=readback_aggregator_kind,
            unit_in=unit_in,
            unit_out=unit_out,
        ):
            return LookupTable(
                calibration_id=calibration_id,
                calibration_revision_id=calibration_revision_id,
                interpolation_kind=interpolation_kind,
                extrapolation_kind=extrapolation_kind,
                invertible=invertible,
                readback_aggregator_kind=readback_aggregator_kind,
                unit_in=unit_in,
                unit_out=unit_out,
            )
        case CompositePartitionBody(
            partition_kind=partition_kind,
            constituent_count=constituent_count,
            partition_parameters=partition_parameters,
            readback_aggregator_kind=readback_aggregator_kind,
        ):
            # Convert list[list[str|float]] to tuple[tuple[str, float], ...]
            params: tuple[tuple[str, float], ...] = tuple(
                (str(pair[0]), float(pair[1])) for pair in partition_parameters
            )
            return CompositePartition(
                partition_kind=partition_kind,
                constituent_count=constituent_count,
                partition_parameters=params,
                readback_aggregator_kind=readback_aggregator_kind,
            )
        case SolverReferenceBody(
            solver_id=solver_id,
            solver_version=solver_version,
            solver_transport_kind=solver_transport_kind,
            residual_tolerance_limit=residual_tolerance_limit,
            singularity_threshold=singularity_threshold,
            invertible=invertible,
            readback_aggregator_kind=readback_aggregator_kind,
        ):
            return SolverReference(
                solver_id=solver_id,
                solver_version=solver_version,
                solver_transport_kind=solver_transport_kind,
                residual_tolerance_limit=residual_tolerance_limit,
                singularity_threshold=singularity_threshold,
                invertible=invertible,
                readback_aggregator_kind=readback_aggregator_kind,
            )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.update_asset_partition_rule
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/{asset_id}/partition-rule",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "PartitionRule validation failed: invalid numeric fields (NaN/Inf), "
                "calibration revision not found or retracted, self-reference detected, "
                "nesting rule violation, or rule shape constraint violated."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Asset is Decommissioned (immutable once retired), "
                "OR a concurrent write to the same asset stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (unknown partition rule kind, "
                "missing required field for kind, malformed UUID, etc.)."
            ),
        },
    },
    summary="Update or clear an asset's partition rule",
)
async def post_asset_partition_rule(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    body: UpdateAssetPartitionRuleRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> dict[str, str]:
    """Update or clear an asset's partition rule.

    POST is used (not PATCH) because the rule is a complete typed VO
    replacement, not a merge patch. Null body clears the rule.
    Returns 200 OK with an empty acknowledgment dict. Any Asset
    carrying a non-None rule is treated as a virtual axis by the
    runtime evaluator and the Plan-bind fan-out validator.
    """
    # Convert Pydantic body to frozen-dataclass union.
    # InvalidPartitionRuleError from _to_partition_rule (raised by
    # __post_init__ validators) is caught by the exception handler in
    # equipment/routes.py and mapped to 400.
    try:
        partition_rule = _to_partition_rule(body.partition_rule)
    except InvalidPartitionRuleError:
        raise

    await handler(
        UpdateAssetPartitionRule(
            asset_id=asset_id,
            partition_rule=partition_rule,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )

    return {}
