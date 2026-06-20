"""MCP tool for conducting a compute Run.

Mirrors `POST /runs/{run_id}/conduct`: accepts a job spec, returns a
structured result summary. Failures land in the return value (not
raised); the LLM caller inspects `succeeded` + `failure` to decide
retry / abort / escalation. Lives at `cora.api` for the same reason as
the route (needs the composition-root `ComputeRuntime` + an
Operation-BC `JobSpec`).
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.api._compute_runtime import ComputeRuntime
from cora.api._conduct_run_route import (
    ConductRunRequest,
    ConductRunResponse,
    build_conduct_job_spec,
    result_to_wire,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class _ToolResult(BaseModel):
    """MCP-shape mirror of `ConductRunResponse` for tool-output validation."""

    run_id: UUID
    succeeded: bool
    status: str | None = None
    job_id: str | None = None
    artifact_uri: str | None = None
    actuation_kind: str | None = None
    failure: str | None = None


def register(
    mcp: FastMCP,
    *,
    get_runtime: Callable[[], ComputeRuntime],
    get_deps: Callable[[], Kernel],
) -> None:
    """Register the `conduct_run` tool on the given MCP server."""

    @mcp.tool(
        name="conduct_run",
        description=(
            "Conduct a compute Run end-to-end: submit the job to the "
            "ComputePort, await its terminal state, and complete the Run on "
            "success or abort it on failure. The server resolves the Run's "
            "Method: if it carries a vetted launch_spec the argv is built "
            "from that recipe and the Run's parameters (omit `command`); "
            "otherwise the legacy raw `command` path is used. The "
            "conduct-observed actuation kind is captured on the Run for "
            "provenance. Returns a structured summary; job failures DO NOT "
            "raise (a malformed request does)."
        ),
    )
    async def conduct_run_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        run_id: Annotated[UUID, Field(description="Target Run's id (must be Running).")],
        body: Annotated[
            ConductRunRequest,
            Field(description="The compute job to run for this Run."),
        ],
    ) -> _ToolResult:
        runtime = get_runtime()
        deps = get_deps()
        job_spec = await build_conduct_job_spec(
            deps, run_id, body, allow_raw=deps.settings.cora_allow_raw_conduct
        )
        result = await runtime.conduct(
            run_id=run_id,
            job_spec=job_spec,
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        wire: ConductRunResponse = result_to_wire(result)
        return _ToolResult(
            run_id=wire.run_id,
            succeeded=wire.succeeded,
            status=wire.status,
            job_id=wire.job_id,
            artifact_uri=wire.artifact_uri,
            actuation_kind=wire.actuation_kind,
            failure=wire.failure,
        )


def register_conduct_run_tools(
    mcp: FastMCP,
    *,
    get_runtime: Callable[[], ComputeRuntime],
    get_deps: Callable[[], Kernel],
) -> None:
    """Register all compute MCP tools (currently just conduct_run)."""
    register(mcp, get_runtime=get_runtime, get_deps=get_deps)


__all__ = ["register", "register_conduct_run_tools"]
