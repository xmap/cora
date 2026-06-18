"""ExecutionPattern closed v1 StrEnum: how a Method's executor consumes work.

Per [[project-compute-modeling-stage0-design]] L3 and
[[project-compute-modeling-synthesis]]:

- `execution_pattern` classifies the WORKLOAD shape of a Method, the
  axis that distinguishes a one-shot batch reconstruction from an
  iterative solver from a streaming consumer.
- Closed v1: exactly three shapes (`Batch`, `Iterative`, `Streaming`).
  The orthogonal scheduling axis (`triggering`: Manual/Scheduled/...)
  is a separate, deferred field, NOT a fourth execution_pattern value.
- New shapes only via an explicit rule-of-three trigger, never ad-hoc,
  mirroring the `ExecutorShape` closed-v1 governance posture.

## Terminal-state semantics per value

- `Batch`: runs to a single terminal (Completed | Aborted).
- `Iterative`: converges or exhausts a budget (Completed=converged |
  Truncated=budget | Aborted). An ITERATIVE Method must declare a
  max_iter-shape or tol-shape stopping key in its parameters_schema
  (enforced at update_method_parameters_schema).
- `Streaming`: consumes until a stop signal or timeout
  (Completed=stop-signal | Truncated=timeout | Aborted).

## Module location

Leaf module under the Method aggregate
(`cora.recipe.aggregates.method.execution_pattern`), mirroring the
`ExecutorShape` enum's placement beside Capability. Imports nothing
from the rest of the aggregate, so state/events/evolver import it
without a cycle.
"""

from enum import StrEnum


class ExecutionPattern(StrEnum):
    """Closed v1 enum of Method workload-execution shapes."""

    BATCH = "Batch"
    """One-shot workload: runs to a single terminal (Gridrec
    reconstruction, a dark/flat baseline reduction, a fixed-grid
    acquisition)."""

    ITERATIVE = "Iterative"
    """Converging workload with a stopping budget/tolerance (FISTA,
    SIRT, optimization loops). Requires a max_iter-shape or tol-shape
    key in parameters_schema; may declare monotone_quality."""

    STREAMING = "Streaming"
    """Unbounded-until-signal workload (live reconstruction, online
    analysis). Consumes until a stop signal or timeout."""


__all__ = ["ExecutionPattern"]
