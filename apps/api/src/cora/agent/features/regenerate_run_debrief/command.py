"""The `RegenerateRunDebrief` command.

Operator-supplied intent dataclass for on-demand RunDebriefer
re-invocation. Carries:

  - `run_id`: which Run to debrief. Existence-checked at
    handler-load time (the same `load_run` the subscriber uses).
  - `parent_decision_id`: optional ref to a prior RunDebrief
    `Decision` (the one being re-evaluated). When supplied, the
    new Decision's `parent_id` is set, forming a PROV-O
    `wasInformedBy` chain. Existence + same-Run-scope checked at
    handler.

  - `agent_id`: which RunDebriefer performs it. `None` (the
    default) means the seeded singleton, which is what every
    existing caller gets. Naming one lets an operator re-debrief
    the same Run under a DIFFERENT approved model, because the
    model served is the named Agent's own `model_ref`, and that
    declaration passed `define_agent`'s catalog gate when the
    Agent was defined. The named Agent must be kind
    `RunDebriefer`; anything else is refused rather than
    attributed. This is the operator half of the buy-vs-build
    comparison: same Run, same prompt, two agents.

The Decision's `decision_id` is server-allocated by the handler
from the IdGenerator port (NOT UUID5-derived; the subscriber's
deterministic-id strategy is specific to terminal-event
at-most-once and doesn't apply here -- on-demand calls use the
Idempotency-Key header for at-most-once).

Discovery of the latest RunDebrief Decision for a Run is OUT OF
SCOPE for v1 (operator passes `parent_decision_id` explicitly via
the request body). The discovery query lands when the UI surfaces
a "regenerate-debrief" button that needs to look it up; pre-trigger
the MCP tool is operator-typed.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RegenerateRunDebrief:
    """Re-invoke RunDebriefer on demand for the given Run."""

    run_id: UUID
    parent_decision_id: UUID | None = None
    agent_id: UUID | None = None
