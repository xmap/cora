"""Pure decider for the `DefineConduit` command.

Pure function: given the current Conduit state (None for a fresh
stream) and a `DefineConduit` command, returns the events to append.
No I/O, no awaits, no side effects.

`now`, `new_id`, and `traversals_logbook_id` are injected by the
application handler from the Clock and IdGenerator ports. The
decider stays pure.

Does NOT verify that `source_zone_id` / `target_zone_id` reference
existing Zones — see `cora.trust.aggregates.conduit.state` for the
eventual-consistency rationale.

## Auto-opens the traversals observation logbook

The decider emits TWO events in one append:
  1. `ConduitDefined` (genesis)
  2. `ConduitLogbookOpened(kind="traversals", schema=...)` declaring
     the per-decision authz audit logbook attached to this Conduit.

This realizes the gate-review L1 lock (per-Conduit traversal logbook
scoping) and the L8 lock (logbook-open events on the parent's main
stream). The schema declared here is the column shape the
`entries_conduit_traversals` table holds; future schema bumps emit a
fresh `ConduitLogbookOpened` with a new logbook_id rather than
mutating the existing one.
"""

from datetime import datetime
from uuid import UUID

from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.trust.aggregates.conduit import (
    LOGBOOK_KIND_TRAVERSALS,
    Conduit,
    ConduitAlreadyExistsError,
    ConduitDefined,
    ConduitLogbookOpened,
    ConduitName,
)
from cora.trust.features.define_conduit.command import DefineConduit

# Schema declaration for the traversals logbook. Column shape matches
# the `entries_conduit_traversals` table.
_TRAVERSALS_SCHEMA = LogbookSchema(
    fields={
        "actor_id": LogbookFieldSpec(
            type="uuid",
            description="The principal that issued the command.",
        ),
        "command_name": LogbookFieldSpec(
            type="string",
            description="Cross-BC command name (for example 'StartRun', 'DefinePolicy').",
        ),
        "decision": LogbookFieldSpec(
            type="string",
            description="'Allow' or 'Deny', from the Authorize port result.",
        ),
        "reason": LogbookFieldSpec(
            type="string",
            description="Free-form reason on Deny; null on Allow.",
        ),
    },
    description=(
        "Per-decision authorization audit log for commands traversing this "
        "Conduit. One row per Authorize port call."
    ),
)


def decide(
    state: Conduit | None,
    command: DefineConduit,
    *,
    now: datetime,
    new_id: UUID,
    traversals_logbook_id: UUID,
) -> list[ConduitDefined | ConduitLogbookOpened]:
    """Decide the events produced by defining a new conduit.

    Invariants:
      - State must be None (defensive AlreadyExists guard against
        UUID collision) -> ConduitAlreadyExistsError
      - Name must be valid -> InvalidConduitNameError
        (via ConduitName VO)
    """
    if state is not None:
        raise ConduitAlreadyExistsError(state.id)
    name = ConduitName(command.name)  # validates + trims
    return [
        ConduitDefined(
            conduit_id=new_id,
            name=name.value,
            source_zone_id=command.source_zone_id,
            target_zone_id=command.target_zone_id,
            occurred_at=now,
        ),
        ConduitLogbookOpened(
            conduit_id=new_id,
            logbook_id=traversals_logbook_id,
            kind=LOGBOOK_KIND_TRAVERSALS,
            schema=_TRAVERSALS_SCHEMA,
            occurred_at=now,
        ),
    ]
