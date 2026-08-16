"""Application handler for the `get_run` query slice.

Cross-BC query-handler shape mirroring `get_plan` / `get_practice`
/ `get_method` / `get_family` / `get_subject` / `get_actor`.

Returns `RunView`, not the bare domain `Run` (slice 13): the aggregate
plus `capture_code` (folded from `external_refs`) and
`observed_capture_path` (resolved from the `run_capture_path` PII
vault), mirroring `get_actor`'s `ActorView` composition exactly --
`bind(deps, *, capture_path_store=...)` resolves both here, in the
handler, not at the route/tool layer: unlike `list_runs` (one shared
handler instance consumed by internal composition-root runtimes that
don't need this value), `get_run`'s handler has no internal caller
today, so nothing forces the vault touch out of it, and keeping the
resolve-and-guard logic in ONE place (not duplicated across `route.py`
and `tool.py`) is strictly better. The route + tool layers do their own
DTO mapping (primitives only) off the returned `RunView`.

Query handlers do NOT emit `causation_id` log fields.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    CapturePathStore,
    Run,
    extract_capture_code,
    load_run,
    load_run_capture_path,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.get_run.query import GetRun

_QUERY_NAME = "GetRun"

_log = get_logger(__name__)


@dataclass(frozen=True)
class RunView:
    """Read-side composition of Run aggregate + capture-path resolution.

    `capture_code` is folded from `run.external_refs`; `None` for a
    Conducted Run. `observed_capture_path` resolves from the
    `run_capture_path` PII vault ONLY when `capture_code` is not
    `None` (a Conducted Run never touches the vault at all): `None`
    when not applicable, `UNOBSERVED_CAPTURE_PATH` (the tombstone) when
    a capture code exists but the vault has no row yet, the real path
    otherwise. Route + MCP-tool layers destructure this into their wire
    DTOs.
    """

    run: Run
    capture_code: str | None
    observed_capture_path: str | None


class Handler(Protocol):
    """Callable interface every get_run handler implements."""

    async def __call__(
        self,
        query: GetRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunView | None: ...


def bind(deps: Kernel, *, capture_path_store: CapturePathStore) -> Handler:
    """Build a get_run handler closed over the shared deps + PII vault."""

    async def handler(
        query: GetRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunView | None:
        _log.info(
            "get_run.start",
            query_name=_QUERY_NAME,
            run_id=str(query.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_run.denied",
                query_name=_QUERY_NAME,
                run_id=str(query.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        run = await load_run(deps.event_store, query.run_id)
        if run is None:
            _log.info(
                "get_run.success",
                query_name=_QUERY_NAME,
                run_id=str(query.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        capture_code = extract_capture_code(run.external_refs)
        observed_capture_path = (
            await load_run_capture_path(capture_path_store, run.id)
            if capture_code is not None
            else None
        )

        _log.info(
            "get_run.success",
            query_name=_QUERY_NAME,
            run_id=str(query.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
        )
        return RunView(
            run=run, capture_code=capture_code, observed_capture_path=observed_capture_path
        )

    return handler


__all__ = [
    "Handler",
    "RunView",
    "bind",
]
