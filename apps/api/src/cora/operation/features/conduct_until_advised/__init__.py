"""Vertical slice for the `ConductUntilAdvised` command (the steered loop wire).

Operator/agent-facing entry point for autonomous experimentation: hands control
to the `Conductor` runtime's `conduct_until_advised`, which walks a recipe-driven
pass block, hands the accumulated evidence to an in-CORA brain after each pass,
and follows its advice on where to measure next until it advises Stop. Returns a
structured `ConductUntilAdvisedResult`; failures (a pass / brain fault, the
absolute ceiling) are encoded in the result, not raised, so a single client
code-path covers every outcome.

    from cora.operation.features import conduct_until_advised

    cmd = conduct_until_advised.ConductUntilAdvised(
        procedure_id=...,
        objective=SteeringObjective(kind=SteeringObjectiveKind.SATISFY, ...),
        space=SteeringSpace(axes=(SteeringAxis(name="theta", lower=-5.0, upper=5.0),)),
        objective_capture_name="rotation_center",
        decide=DecidePortConfig(substrate="grid_walk"),
    )
    handler = conduct_until_advised.bind(deps, conductor=conductor, expansion_port=expander)
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.conduct_until_advised import tool
from cora.operation.features.conduct_until_advised.command import (
    ConductUntilAdvised,
    ConductUntilAdvisedResult,
)
from cora.operation.features.conduct_until_advised.handler import Handler, bind
from cora.operation.features.conduct_until_advised.route import (
    ConductUntilAdvisedRequest,
    ConductUntilAdvisedResponse,
    router,
)

__all__ = [
    "ConductUntilAdvised",
    "ConductUntilAdvisedRequest",
    "ConductUntilAdvisedResponse",
    "ConductUntilAdvisedResult",
    "Handler",
    "bind",
    "router",
    "tool",
]
