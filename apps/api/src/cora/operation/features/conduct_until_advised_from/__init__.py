"""Vertical slice for the `ConductUntilAdvisedFrom` command (steered RESUME wire).

Operator/agent-facing resume for autonomous experimentation: resume a Held
GP-steered Procedure by re-seeding the in-CORA brain from the recorded closed
passes and continuing the measure-then-advise loop at the open frontier. The
already-measured passes are neither re-driven nor re-measured (strategy A per
[[project_resumable_conduct_design]]). Returns a structured
`ConductUntilAdvisedFromResult`; loop failures are encoded in the result, not
raised.

    from cora.operation.features import conduct_until_advised_from

    handler = conduct_until_advised_from.bind(
        deps, conductor=conductor, expansion_port=expander, outcome_lookup=lookup
    )
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.conduct_until_advised_from import tool
from cora.operation.features.conduct_until_advised_from.command import (
    ConductUntilAdvisedFrom,
    ConductUntilAdvisedFromResult,
)
from cora.operation.features.conduct_until_advised_from.handler import Handler, bind
from cora.operation.features.conduct_until_advised_from.route import (
    ConductUntilAdvisedFromRequest,
    ConductUntilAdvisedFromResponse,
    router,
)

__all__ = [
    "ConductUntilAdvisedFrom",
    "ConductUntilAdvisedFromRequest",
    "ConductUntilAdvisedFromResponse",
    "ConductUntilAdvisedFromResult",
    "Handler",
    "bind",
    "router",
    "tool",
]
