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

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.api._compute_runtime import ComputeRunResult, ComputeRuntime
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.ports.compute_port import ComputeResources, JobSpec
from cora.recipe.aggregates.method import Method, build_argv, load_method
from cora.recipe.aggregates.plan import load_plan
from cora.recipe.aggregates.practice import load_practice
from cora.run.aggregates.run import Run, load_run

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

    command: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=_COMMAND_MAX,
        description=(
            "Raw argv (legacy path), only for a Method with NO launch_spec. "
            "Forbidden (422) when the Method has a launch_spec: the server "
            "builds the argv from the vetted recipe instead."
        ),
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


def _resources(body: ConductRunRequest) -> ComputeResources:
    if body.resources is None:
        return ComputeResources()
    return ComputeResources(
        gpu_count=body.resources.gpu_count,
        gpu_memory_gb=body.resources.gpu_memory_gb,
        system_ram_gb=body.resources.system_ram_gb,
        cpus=body.resources.cpus,
    )


def build_job_spec(body: ConductRunRequest) -> JobSpec:
    """Build a raw-path `JobSpec` from the request body (caller argv).

    Only used when the Method has NO launch_spec; the dispatcher guards
    that `command` is present before calling this.
    """
    return JobSpec(
        command=tuple(body.command or ()),
        input_uris=tuple(body.input_uris),
        output_uri=body.output_uri,
        parameters=body.parameters,
        resources=_resources(body),
    )


async def _resolve_method_for_run(deps: Kernel, run_id: UUID) -> tuple[Run | None, Method | None]:
    """Best-effort Run -> Plan -> Practice -> Method resolution.

    Returns `(run, method)`; either is None if a link is missing (a
    broken / absent chain falls back to the raw path rather than 500ing).
    """
    run = await load_run(deps.event_store, run_id)
    if run is None:
        return None, None
    plan = await load_plan(deps.event_store, run.plan_id)
    if plan is None:
        return run, None
    practice = await load_practice(deps.event_store, plan.practice_id)
    if practice is None:
        return run, None
    method = await load_method(deps.event_store, practice.method_id)
    return run, method


async def build_conduct_job_spec(
    deps: Kernel, run_id: UUID, body: ConductRunRequest, *, allow_raw: bool
) -> JobSpec:
    """Resolve the Run's Method and build the JobSpec (dual-mode).

    Shared by the REST route and the MCP tool. launch_spec present ->
    the server builds the argv from the vetted recipe + the Run's
    effective_parameters (a raw `command` in the body is rejected). No
    launch_spec -> the legacy raw-command path, gated by `allow_raw`.
    Rejections raise `HTTPException` (REST maps it; the MCP tool wraps it
    as an error result). build_argv's MissingLaunchParameter /
    UnsafeLaunchUri errors propagate and map to 400 app-wide.
    """
    run, method = await _resolve_method_for_run(deps, run_id)
    if method is not None and method.launch_spec is not None:
        if body.command is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "this Method has a launch_spec; omit the raw `command` "
                    "(the server builds the argv)."
                ),
            )
        effective = run.effective_parameters if run is not None else {}
        argv = build_argv(
            method.launch_spec,
            effective,
            input_uris=tuple(body.input_uris),
            output_uri=body.output_uri,
        )
        return JobSpec(
            command=argv,
            input_uris=tuple(body.input_uris),
            output_uri=body.output_uri,
            parameters=dict(effective),
            resources=_resources(body),
        )

    if not allow_raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="raw-command conduct is disabled and this Method has no launch_spec.",
        )
    if body.command is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="this Method has no launch_spec; a raw `command` is required.",
        )
    return build_job_spec(body)


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


def _get_deps(request: Request) -> Kernel:
    deps: Kernel = request.app.state.deps
    return deps


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/conduct",
    status_code=status.HTTP_200_OK,
    response_model=ConductRunResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "The Run's parameters do not satisfy the Method's launch_spec, or a URI is unsafe."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the underlying Run transition.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Body failed schema validation, or a raw `command` was supplied for a "
                "launch_spec Method, or a raw `command` is missing / disabled."
            ),
        },
    },
    summary="Conduct a compute Run: submit the job, await it, then complete or abort the Run.",
)
async def post_runs_conduct(
    run_id: Annotated[UUID, Path(description="Target Run's id (must be Running).")],
    body: ConductRunRequest,
    runtime: Annotated[ComputeRuntime, Depends(_get_runtime)],
    deps: Annotated[Kernel, Depends(_get_deps)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductRunResponse:
    """Conduct a compute Run end-to-end. Failures land in the response body."""
    job_spec = await build_conduct_job_spec(
        deps, run_id, body, allow_raw=deps.settings.cora_allow_raw_conduct
    )
    result = await runtime.conduct(
        run_id=run_id,
        job_spec=job_spec,
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
    "build_conduct_job_spec",
    "build_job_spec",
    "register_conduct_run_routes",
    "result_to_wire",
    "router",
]
