"""Resolved-steps replay helper for the `reconduct_procedure` handler.

The resume path replays a halted conduct from PINNED resolved steps rather
than re-deriving the step list. This module locates the
`ResolvedStepsRecorded` provenance event (pinned once at conduct start by
`_conduct_preparation.resolve_and_pin_conduct_steps`) in a Procedure stream so
the handler can parse `resolved_steps` back into `Step`s via
`conductor.steps_from_payload` and hand them to `Conductor.execute_from`.

Sibling of `_recipe_replay.find_recipe_expansion_record` (the recipe
genesis provenance finder), kept separate because that module's tuple of
helpers is recipe-expansion-specific. This is the SECOND handler-tier
payload-direct reader; per the replay-design rule-of-three note, when a
THIRD lands the two `find_*_record` head-scanners should hoist to a
generic `cora.infrastructure.event_payload` helper.
"""

from collections.abc import Iterable

from cora.infrastructure.ports.event_store import StoredEvent


def find_resolved_steps_record(
    stored_events: Iterable[StoredEvent],
) -> StoredEvent | None:
    """Locate the `ResolvedStepsRecorded` event in a Procedure stream.

    Scans linearly from head, returns the first match, early-exits on the
    first hit. A conduct pins exactly one `ResolvedStepsRecorded` at start
    (only while the Procedure is `Defined`), so a Held Procedure that has
    been conducted carries exactly one; head-scan returns it.

    Returns `None` when no match. The caller decides whether None is an
    error: the `reconduct_procedure` handler raises
    `ResolvedStepsRecordNotFoundError` (a Held Procedure missing its pinned
    resolved steps is corruption, not an operational outcome).
    """
    for event in stored_events:
        if event.event_type == "ResolvedStepsRecorded":
            return event
    return None
