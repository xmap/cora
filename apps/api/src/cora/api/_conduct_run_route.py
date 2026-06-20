"""HTTP route for conducting a compute Run: `POST /runs/{run_id}/conduct`.

The external entry point for the `ComputeRuntime`. The caller supplies
the concrete job to run (command argv + input/output URIs + optional
parameters/resources); the runtime submits it to the wired
`ComputePort`, awaits the terminal state, and transitions the Run
(complete on success, abort on failure), capturing actuation provenance
on the Run terminal event.

## Why this route lives at `cora.api`, not in a BC slice

The route needs both a `JobSpec` (an Operation-BC type) and the
`ComputeRuntime` (composition-root owned). tach forbids
`cora.run -> cora.operation`, and the runtime is not a BC handler, so
the route cannot live in the Run or Operation BC. It lives here at the
composition root, the one module that depends on both, exactly as the
`ComputeRuntime` itself does. It reads the runtime off `app.state`
(no import coupling), mirroring how `conduct_procedure`'s route reads
its handler off `app.state.operation`.

## Caller-supplied job, Authorize-gated

Like `conduct_procedure` (which accepts a caller-supplied step list of
control addresses + values), this accepts a caller-supplied job spec.
The security boundary is the Authorize port + principal on the
underlying `complete_run` / `abort_run` commands, not a restriction on
the payload shape.

## Response code: always 200, failures in body

Conduct is an orchestration call, not CRUD. A failed job (the solver
exited non-zero, timed out, or the Run could not be completed) is a
NORMAL outcome the operator triages: it lands in the response body as
`succeeded=False` + a `failure` string, not an HTTP 4xx/5xx. Only
malformed JSON (422) and authz deny (403) map to HTTP error codes.
Mirrors `conduct_procedure` and CI-runner APIs.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Path, Request, status
from pydantic import BaseModel, Field

from cora.api._compute_runtime import ComputeRunResult, ComputeRuntime
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.ports.compute_port import ComputeResources, JobSpec

_COMMAND_MAX = 256
"""A job command is an argv of at most this many tokens; a generous
ceiling that still bounds an obviously-malformed request."""

_URI_BATCH_MAX = 512
"""Cap on input URIs a single job names. Larger fan-ins split client-side."""


class ComputeResourcesRequest(BaseModel):
    """JSON wire shape for `ComputeResources` (all optional).

    Mirrors the bound ComputeNode Asset's GPU/RAM settings. The
    local-process adapter ignores these (a subprocess takes what the
    box has); a future scheduler adapter maps them to `--gres` / `--mem`.
    """

    gpu_count: int = Field(default=0, ge=0)
    gpu_memory_gb: float | None = Field(default=None, gt=0)
    system_ram_gb: float | None = Field(default=None, gt=0)
    cpus: int | None = Field(default=None, gt=0)

    model_config = {"extra": "forbid"}


class ConductRunRequest(BaseModel):
    """Body for `POST /runs/{run_id}/conduct`."""

    command: list[str] = Field(
        ...,
        min_length=1,
        max_length=_COMMAND_MAX,
        description="The argv the substrate launches (e.g. tomopy recon --algorithm sirt).",
    )
    input_uris: list[str] = Field(
        default_factory=list[str],
        max_length=_URI_BATCH_MAX,
        description="URIs the job reads (e.g. the raw projection Dataset's Distribution).",
    )
    output_uri: str | None = Field(
        default=None,
        description="Where the job writes its artifact; recorded as the output Dataset uri.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict[str, Any],
        description="Validated parameter set (typically the Run's effective_parameters).",
    )
    resources: ComputeResourcesRequest | None = Field(
        default=None,
        description="Optional resource shape; defaults to unspecified.",
    )

    model_config = {"extra": "forbid"}


class ConductRunResponse(BaseModel):
    """Response body for the conduct-run-compute route.

    `succeeded` is the canonical pass/fail bit. `status` is the job's
    terminal `ComputeStatus` value (or null when the job never started).
    `actuation_kind` is read-only operator visibility; the promotion
    gate reads it server-side off the Run stream, never back from here.
    `failure` is non-null iff `succeeded` is False.
    """

    run_id: UUID
    succeeded: bool
    status: str | None = None
    job_id: str | None = None
    artifact_uri: str | None = None
    actuation_kind: str | None = None
    failure: str | None = None


def build_job_spec(body: ConductRunRequest) -> JobSpec:
    """Build a Conductor `JobSpec` from the request body.

    Public because `tool.py` calls it too (MCP + REST share the wire
    schema). Resources default to unspecified when the body omits them.
    """
    resources = (
        ComputeResources(
            gpu_count=body.resources.gpu_count,
            gpu_memory_gb=body.resources.gpu_memory_gb,
            system_ram_gb=body.resources.system_ram_gb,
            cpus=body.resources.cpus,
        )
        if body.resources is not None
        else ComputeResources()
    )
    return JobSpec(
        command=tuple(body.command),
        input_uris=tuple(body.input_uris),
        output_uri=body.output_uri,
        parameters=body.parameters,
        resources=resources,
    )


def result_to_wire(result: ComputeRunResult) -> ConductRunResponse:
    """Build a `ConductRunResponse` from the runtime's result.

    Public because `tool.py` calls it too.
    """
    return ConductRunResponse(
        run_id=result.run_id,
        succeeded=result.succeeded,
        status=result.status.value if result.status is not None else None,
        job_id=str(result.job_id) if result.job_id is not None else None,
        artifact_uri=result.artifact_ref.uri if result.artifact_ref is not None else None,
        actuation_kind=result.actuation_kind.value if result.actuation_kind is not None else None,
        failure=result.failure,
    )


def _get_runtime(request: Request) -> ComputeRuntime:
    runtime: ComputeRuntime = request.app.state.compute_runtime
    return runtime


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/conduct",
    status_code=status.HTTP_200_OK,
    response_model=ConductRunResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the underlying Run transition.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation (empty command, bad field).",
        },
    },
    summary="Conduct a compute Run: submit the job, await it, then complete or abort the Run.",
)
async def post_runs_conduct(
    run_id: Annotated[UUID, Path(description="Target Run's id (must be Running).")],
    body: ConductRunRequest,
    runtime: Annotated[ComputeRuntime, Depends(_get_runtime)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductRunResponse:
    """Conduct a compute Run end-to-end. Failures land in the response body."""
    result = await runtime.conduct(
        run_id=run_id,
        job_spec=build_job_spec(body),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)


def register_conduct_run_routes(app: FastAPI) -> None:
    """Register the conduct-run-compute route on the FastAPI app."""
    app.include_router(router)


__all__ = [
    "ComputeResourcesRequest",
    "ConductRunRequest",
    "ConductRunResponse",
    "build_job_spec",
    "register_conduct_run_routes",
    "result_to_wire",
    "router",
]
