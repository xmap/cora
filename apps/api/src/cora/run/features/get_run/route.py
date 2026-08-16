"""HTTP route for the `get_run` query slice.

`GET /runs/{run_id}` returns 200 + RunResponse on hit, 404 on miss.

Response shape: `{id, name, plan_id, subject_id, raid, status}`.
`subject_id` and `raid` are null when not set (calibration runs, or
Runs not registered against a research activity respectively).

`capture_code` / `observed_capture_path` (slice 13) and
`proposal_number` / `esaf_number` / `esaf_doi` (slice 14a) are resolved
inside `get_run`'s own `Handler` (`handler.py`'s `RunView`), mirroring
`get_actor`'s `ActorView` exactly: this route only destructures the
already-composed view into its wire DTO, the same shape every other
field on this DTO already follows.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.get_run.handler import Handler
from cora.run.features.get_run.query import GetRun


class RunResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value. `subject_id` is null for calibration / dark-field
    runs. `raid` is null when no Research Activity Identifier was
    supplied at start time (additive retrofit).

    `override_parameters` and `effective_parameters` carry the
    parameter set: overrides the operator supplied at start
    time, and the resolved merge of Plan defaults + overrides that
    actually governed this Run. Both default `{}`. `trigger_source`
    captures what initiated the Run (None if unrecorded).

    `campaign_id` (6i-c) is the Campaign this Run is a member of, set
    either at start time (StartRun.campaign_id) or post-hoc via
    add_run_to_campaign. None when the Run is standalone (not part of
    any Campaign). Closes design-memo Watch #17 (per Caution-design
    cross-BC consistency precedent).

    `capture_code` (slice 13) is the deployment-declared capture
    identifier a witnessed genesis stamps onto `external_refs`. None
    for a Conducted Run. NOT personal data.

    `observed_capture_path` (slice 13) is the areaDetector file the
    capture wrote, resolved from the `run_capture_path` PII vault:
    `None` when `capture_code` is `None` (not applicable, a Conducted
    Run); the tombstone literal (`UNOBSERVED_CAPTURE_PATH`) when a
    capture code exists but the vault has no row yet (never observed,
    or rejected by the dual-clock guard); the real path otherwise.
    This IS the authorized operator surface meant to let them find the
    file for `ingest_scan`.

    `proposal_number` / `esaf_number` / `esaf_doi` (slice 14a), each
    paired with its own `*_observed_at` (the substrate's own reading
    time, for judging staleness -- these PVs persist across beamtimes
    with no in-band freshness signal), resolve from the
    `run_experiment_identity` vault under the same `capture_code is
    not None` condition. No tombstone: `None` here means either "not
    applicable" (Conducted Run) or "nothing recorded yet"; `capture_code`
    already distinguishes the two. Institutional identifiers for a
    funded experiment, not personal data.
    """

    id: UUID
    name: str = Field(..., max_length=RUN_NAME_MAX_LENGTH)
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None
    status: str
    override_parameters: dict[str, Any] = Field(default_factory=dict)
    effective_parameters: dict[str, Any] = Field(default_factory=dict)
    trigger_source: str | None = None
    campaign_id: UUID | None = None
    capture_code: str | None = None
    observed_capture_path: str | None = None
    proposal_number: str | None = None
    proposal_number_observed_at: datetime | None = None
    esaf_number: str | None = None
    esaf_number_observed_at: datetime | None = None
    esaf_doi: str | None = None
    esaf_doi_observed_at: datetime | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.get_run
    return handler


router = APIRouter(tags=["run"])


@router.get(
    "/runs/{run_id}",
    status_code=status.HTTP_200_OK,
    response_model=RunResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No run exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a run by id",
)
async def get_runs(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> RunResponse:
    view = await handler(
        GetRun(run_id=run_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    run = view.run
    return RunResponse(
        id=run.id,
        name=run.name.value,
        plan_id=run.plan_id,
        subject_id=run.subject_id,
        raid=run.raid,
        status=run.status.value,
        override_parameters=run.override_parameters,
        effective_parameters=run.effective_parameters,
        trigger_source=run.trigger_source,
        campaign_id=run.campaign_id,
        capture_code=view.capture_code,
        observed_capture_path=view.observed_capture_path,
        proposal_number=view.proposal_number,
        proposal_number_observed_at=view.proposal_number_observed_at,
        esaf_number=view.esaf_number,
        esaf_number_observed_at=view.esaf_number_observed_at,
        esaf_doi=view.esaf_doi,
        esaf_doi_observed_at=view.esaf_doi_observed_at,
    )
