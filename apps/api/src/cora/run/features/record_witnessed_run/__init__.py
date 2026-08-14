"""Vertical slice for the `RecordWitnessedRun` command: the witnessed genesis.

In-process-only by design: no REST route, no MCP tool. Module-as-
namespace surface, symmetric with the other genesis slice:

    from cora.run.features import record_witnessed_run

    cmd = record_witnessed_run.RecordWitnessedRun(
        name="...", plan_id=..., capture_code=..., monitor_source_id=...,
        trigger="Monitor",
    )
    handler = record_witnessed_run.bind(deps)
    run_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.record_witnessed_run import tool
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run.context import RunWitnessedStartContext
from cora.run.features.record_witnessed_run.decider import decide
from cora.run.features.record_witnessed_run.handler import Handler, bind
from cora.run.features.record_witnessed_run.route import router

__all__ = [
    "Handler",
    "RecordWitnessedRun",
    "RunWitnessedStartContext",
    "bind",
    "decide",
    "router",
    "tool",
]
