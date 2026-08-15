"""Vertical slice for the `RecordWitnessedRunOutcome` command: the witnessed terminal.

In-process-only by design: no REST route, no MCP tool, mirroring
`record_witnessed_run`. Module-as-namespace surface:

    from cora.run.features import record_witnessed_run_outcome

    cmd = record_witnessed_run_outcome.RecordWitnessedRunOutcome(
        run_id=..., capture_code=..., observed_phase=CapturePhase.ENDED,
        observed_at=..., monitor_source_id=..., trigger="Monitor",
    )
    handler = record_witnessed_run_outcome.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.record_witnessed_run_outcome import tool
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.run.features.record_witnessed_run_outcome.decider import decide
from cora.run.features.record_witnessed_run_outcome.handler import Handler, bind
from cora.run.features.record_witnessed_run_outcome.route import router

__all__ = [
    "Handler",
    "RecordWitnessedRunOutcome",
    "bind",
    "decide",
    "router",
    "tool",
]
