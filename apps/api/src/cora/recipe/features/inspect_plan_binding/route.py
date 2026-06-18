"""HTTP route for the `inspect_plan_binding` query slice.

`POST /plans/inspect-binding` accepts `{practice_id, asset_ids}`
and returns the binding diagnostic. POST (not GET) because the
asset_ids list is variable-length and belongs in a body.

Missing upstream entities surface as 404 via the recipe BC's
shared `_handle_not_found` exception mapping (PracticeNotFound,
MethodNotFound, AssetNotFound, CapabilityNotFound, FamilyNotFound
are already registered).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.features.inspect_plan_binding.handler import Handler
from cora.recipe.features.inspect_plan_binding.query import InspectPlanBinding


class InspectPlanBindingRequest(BaseModel):
    """Wire-side input for the inspect_plan_binding endpoint."""

    practice_id: UUID
    asset_ids: list[UUID] = Field(..., min_length=1)


class WiredAssetItem(BaseModel):
    """Per-wired-Asset binding contribution on the wire.

    `family_ids` and `contributed_affordances` are sorted for
    deterministic client diffs / cache validation.
    """

    asset_id: UUID
    asset_name: str
    condition: str | None
    lifecycle: str
    family_ids: list[UUID]
    contributed_affordances: list[str]


class CandidateAssetItem(BaseModel):
    """Per-Asset candidate for a missing affordance on the wire.

    `contributing_family_ids` is deliberately named to differ from
    `WiredAssetItem.family_ids`: it lists ONLY the candidate's
    Families that declare the parent missing affordance, not the
    candidate's full Family set. Other state (condition, lifecycle)
    is unfiltered so the operator can see Faulted / Decommissioned
    candidates and decide whether to act.
    """

    asset_id: UUID
    asset_name: str
    condition: str | None
    lifecycle: str
    contributing_family_ids: list[UUID] = Field(
        ...,
        description=(
            "Subset of the candidate's Families that declare the parent "
            "missing affordance, NOT the candidate's full Family set. "
            "Naming distinguishes this from WiredAssetItem.family_ids "
            "(the full set) so SDK consumers don't naively union the two."
        ),
    )


class MissingAffordanceCandidatesItem(BaseModel):
    """Per-missing-affordance group on the wire.

    `affordance` is one of the entries in `missing_affordances`.
    `candidates` is sorted by asset_id string form (mirrors the
    wired_assets ordering convention). Empty list means the
    facility has no Asset that could cover this requirement.
    """

    affordance: str
    candidates: list[CandidateAssetItem]


class InspectPlanBindingResponse(BaseModel):
    """Wire-side diagnostic returned by the endpoint.

    `missing_family_ids` and `missing_affordances` are sorted lists;
    empty means that dimension is satisfied. `binding_status` is
    the at-a-glance verdict (Satisfied / MissingFamilies /
    MissingAffordances / MissingCapability).

    `missing_affordance_candidates` enumerates, per missing
    affordance, other facility Assets whose Families declare it.
    Empty when no affordances are missing; in in-memory test mode
    (no pool) the projection-backed lookup is skipped and this
    stays empty regardless.
    """

    practice_id: UUID
    method_id: UUID
    capability_id: UUID | None
    method_needed_family_ids: list[UUID]
    capability_required_affordances: list[str]
    wired_assets: list[WiredAssetItem]
    missing_family_ids: list[UUID]
    missing_affordances: list[str]
    missing_affordance_candidates: list[MissingAffordanceCandidatesItem]
    binding_status: str


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.inspect_plan_binding
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/plans/inspect-binding",
    status_code=status.HTTP_200_OK,
    response_model=InspectPlanBindingResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Practice, Method, Asset, Capability, or Family not found.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Preview a Plan binding without defining it",
)
async def inspect_plan_binding(
    body: InspectPlanBindingRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> InspectPlanBindingResponse:
    view = await handler(
        InspectPlanBinding(
            practice_id=body.practice_id,
            asset_ids=frozenset(body.asset_ids),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return InspectPlanBindingResponse(
        practice_id=view.practice_id,
        method_id=view.method_id,
        capability_id=view.capability_id,
        method_needed_family_ids=sorted(view.method_needed_family_ids, key=str),
        capability_required_affordances=sorted(
            a.value for a in view.capability_required_affordances
        ),
        wired_assets=[
            WiredAssetItem(
                asset_id=item.asset_id,
                asset_name=item.asset_name,
                condition=item.condition.value if item.condition is not None else None,
                lifecycle=item.lifecycle.value,
                family_ids=sorted(item.family_ids, key=str),
                contributed_affordances=sorted(a.value for a in item.contributed_affordances),
            )
            for item in view.wired_assets
        ],
        missing_family_ids=sorted(view.missing_family_ids, key=str),
        missing_affordances=sorted(a.value for a in view.missing_affordances),
        missing_affordance_candidates=[
            MissingAffordanceCandidatesItem(
                affordance=entry.affordance.value,
                candidates=[
                    CandidateAssetItem(
                        asset_id=candidate.asset_id,
                        asset_name=candidate.asset_name,
                        condition=(
                            candidate.condition.value if candidate.condition is not None else None
                        ),
                        lifecycle=candidate.lifecycle.value,
                        contributing_family_ids=sorted(candidate.contributing_family_ids, key=str),
                    )
                    for candidate in entry.candidates
                ],
            )
            for entry in view.missing_affordance_candidates
        ],
        binding_status=view.binding_status.value,
    )
