"""Resolved-steps replay helper for the `conduct_from_procedure` handler.

The resume path replays a halted conduct from PINNED resolved steps rather
than re-deriving the step list. This module locates the
`ResolvedStepsRecorded` provenance event (pinned at conduct start by
`_conduct_preparation.resolve_and_pin_conduct_steps`, at least once and
possibly more, see `find_resolved_steps_record`) in a Procedure stream so
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
    first hit.

    A stream may carry MORE than one pin, so head-scan is a choice rather
    than a lookup of the only candidate, and when it bites this returns the
    ABANDONED attempt rather than the one that ran.

    `decide_resolved_steps_recorded` guards on status alone, so any conduct
    that fails after the pin and before `start_procedure` leaves the
    Procedure `Defined` and the retry pins again. Three such paths exist on
    the steered entry point alone: `UnsupportedClosingStepsError`, the
    `ValueError` from `build_decide_port` (raised outside the handler's
    `try`), and `_validate_steering_wire`, which runs before
    `_start_procedure`.

    The recipe MAIN steps are protected: `verify_steps_hash` rejects a
    re-expansion that drifts. The gap is `expand_pseudoaxis`, which runs
    after that check and is not hash-covered. For a Run-phase Procedure it
    resolves constituents from the parent Run's live `Plan.wires`, so a
    rewire between attempts yields a materially different second pin, and
    this function replays the first. A reader that needs the pin which
    actually governed the conduct must not use this function.

    Returns `None` when no match. The caller decides whether None is an
    error: the `conduct_from_procedure` handler raises
    `ResolvedStepsRecordNotFoundError` (a Held Procedure missing its pinned
    resolved steps is corruption, not an operational outcome).
    """
    for event in stored_events:
        if event.event_type == "ResolvedStepsRecorded":
            return event
    return None
