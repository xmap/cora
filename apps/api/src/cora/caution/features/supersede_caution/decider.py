"""Pure decider for the `SupersedeCaution` command.

Cross-aggregate transition: parent goes `Active -> Superseded` while a
new child caution is registered with `parent_id=<parent>`.
Both event streams are written atomically by the handler via
`EventStore.append_streams`; the decider returns BOTH event lists
typed as `SupersessionEvents` so the handler doesn't need to guess
which stream gets which event. Mirrors Safety's `amend_clearance`
decider exactly.

## Validation

  - Parent state must be Active -> `CautionCannotSupersedeError`
  - Child fields validated identically to `register_caution` decider
    (text/workaround/tags via VOs; expires_at strictly future).
  - Child `target` MUST equal parent `target` ->
    `InvalidCautionSupersedeTargetError`. Supersession preserves
    target.

The superseding actor's id lives on the envelope; the decider neither
reads nor writes it. The child's `authored_by` IS carried on the
genesis event payload (denorm convenience).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cora.caution.aggregates.caution import (
    Caution,
    CautionRegistered,
    CautionSuperseded,
    CautionTag,
    CautionText,
    CautionWorkaround,
    ensure_expires_at_future,
    ensure_supersedable,
    ensure_target_preserved,
)
from cora.caution.features.supersede_caution.command import SupersedeCaution
from cora.caution.features.supersede_caution.context import CautionSupersessionContext
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class SupersessionEvents:
    """The two event lists produced by a supersession, one per stream.

    `parent_events`: appended to the parent caution's stream.
    `child_events`: appended to the (new) child caution's stream.

    Both lists are non-empty under normal operation; the handler hands
    them to `EventStore.append_streams` as a single atomic batch.
    """

    parent_events: list[CautionSuperseded]
    child_events: list[CautionRegistered]


def decide(
    state: Caution | None,
    command: SupersedeCaution,
    *,
    context: CautionSupersessionContext,
    now: datetime,
    new_id: UUID,
    authored_by: ActorId,
) -> SupersessionEvents:
    """Decide the parent+child events produced by superseding an Active caution.

    Invariants:
      - Parent state must be Active -> CautionCannotSupersedeError
        (via ensure_supersedable)
      - Text must be valid -> InvalidCautionTextError
        (via CautionText VO)
      - Workaround must be valid -> InvalidCautionWorkaroundError
        (via CautionWorkaround VO)
      - Each tag must be valid -> InvalidCautionTagError
        (via CautionTag VO)
      - expires_at (when set) must be strictly future
        -> InvalidCautionExpiresAtError
      - Child target must equal parent target
        -> InvalidCautionSupersedeTargetError
        (via ensure_target_preserved)

    `state` is conceptually the child's prior state (always None
    because the child is being created here). The parent's state lives
    in `context.parent`.

    `authored_by` is handler-injected from the request envelope's
    `principal_id`; the command surface omits it (mirroring
    `register_caution`) so callers cannot spoof a different author.
    """
    _ = state  # The child is genesis; this slice never sees a prior child state.

    parent = context.parent
    ensure_supersedable(parent)

    # ---- Validate the child's fields (mirrors register_caution decider) ----

    text = CautionText(command.text)
    workaround = CautionWorkaround(command.workaround)
    tags = frozenset(CautionTag(t) for t in command.tags)

    ensure_expires_at_future(command.expires_at, now)
    ensure_target_preserved(parent.target, command.target)

    parent_events = [
        CautionSuperseded(
            caution_id=parent.id,
            superseded_by_caution_id=new_id,
            occurred_at=now,
        )
    ]
    child_events = [
        CautionRegistered(
            caution_id=new_id,
            target=command.target,
            category=command.category.value,
            severity=command.severity.value,
            text=text.value,
            workaround=workaround.value,
            tags=frozenset(t.value for t in tags),
            authored_by=authored_by,
            expires_at=command.expires_at,
            propagate_to_children=command.propagate_to_children,
            parent_id=parent.id,
            occurred_at=now,
        )
    ]
    return SupersessionEvents(parent_events=parent_events, child_events=child_events)
