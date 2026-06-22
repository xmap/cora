"""Visit's update-handler factory (thin wrapper).

Closes over Visit-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

## Hoist trigger

Visit ships eight transition slices day one (`record_visit_arrival` /
`start_visit` / `hold_visit` / `resume_visit` / `complete_visit` /
`cancel_visit` / `abort_visit` / `void_visit`). Eight identical
longhand bodies fire the rule-of-three signal at slice-creation time,
so the factory hoists immediately, matching the precedent set by
`_campaign_update_handler` (Campaign hoisted at 5 slices),
`_clearance_update_handler` (Safety hoisted at 6 slices), and
`_supply_update_handler` (Supply hoisted at 5 slices).

## Per-aggregate scoping

The factory scopes to the Visit aggregate (not the Trust BC) so a
future Trust-sibling aggregate would get its own factory rather than
parameterizing this one. Same per-aggregate scoping rationale as
`_clearance_update_handler` / `_campaign_update_handler`.

## Visit-side knobs closed over

  - `stream_type = "Visit"`.
  - `target_id_attr = "visit_id"` -- every Visit transition command
    exposes `visit_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Trust BC.
  - The four codec functions imported from
    `cora.trust.aggregates.visit`.
"""

from collections.abc import Callable, Sequence

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.trust.aggregates.visit import (
    VisitEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.trust.errors import UnauthorizedError


def make_visit_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[VisitEvent]],
):
    """Build an update-style handler for one Visit transition slice."""
    return make_update_handler(
        deps,
        stream_type="Visit",
        target_id_attr="visit_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
    )


__all__ = ["make_visit_update_handler"]
