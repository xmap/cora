"""Vertical slice for the `ConductUntilConverged` command (slice 6c).

Operator-facing AUTO-align entry point: hands control to the `Conductor`
runtime's `conduct_until_converged`, which iterates a measure-correct pass
block until a loop-evaluated criterion over the captures bus is met OR the
patience cap trips. Returns a structured `ConductUntilConvergedResult`;
failures (a never-converged cap-abort, an in-pass fault) are encoded in the
result, not raised, so a single client code-path covers every outcome.

    from cora.operation.features import conduct_until_converged

    cmd = conduct_until_converged.ConductUntilConverged(
        procedure_id=...,
        convergence_capture_name="rotation_center_offset",
        criterion=WithinToleranceCriterion(expected=0.0, tolerance=0.5),
    )
    handler = conduct_until_converged.bind(deps, conductor=conductor, expansion_port=expander)
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.conduct_until_converged import tool
from cora.operation.features.conduct_until_converged.command import (
    ConductUntilConverged,
    ConductUntilConvergedResult,
)
from cora.operation.features.conduct_until_converged.handler import Handler, bind
from cora.operation.features.conduct_until_converged.route import (
    ConductUntilConvergedRequest,
    ConductUntilConvergedResponse,
    router,
)

__all__ = [
    "ConductUntilConverged",
    "ConductUntilConvergedRequest",
    "ConductUntilConvergedResponse",
    "ConductUntilConvergedResult",
    "Handler",
    "bind",
    "router",
    "tool",
]
