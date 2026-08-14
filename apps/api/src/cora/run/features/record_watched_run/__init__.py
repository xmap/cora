"""Vertical slice for the `RecordWatchedRun` command: the watched genesis.

In-process-only by design: no REST route, no MCP tool. Module-as-
namespace surface, symmetric with the other genesis slice:

    from cora.run.features import record_watched_run

    cmd = record_watched_run.RecordWatchedRun(
        name="...", plan_id=..., capture_code=..., monitor_source_id=...,
        trigger="Monitor",
    )
    handler = record_watched_run.bind(deps)
    run_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.run.features.record_watched_run import tool
from cora.run.features.record_watched_run.command import RecordWatchedRun
from cora.run.features.record_watched_run.context import RunWatchedStartContext
from cora.run.features.record_watched_run.decider import decide
from cora.run.features.record_watched_run.handler import Handler, bind
from cora.run.features.record_watched_run.route import router

__all__ = [
    "Handler",
    "RecordWatchedRun",
    "RunWatchedStartContext",
    "bind",
    "decide",
    "router",
    "tool",
]
