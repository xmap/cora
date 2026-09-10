"""Evolver: replay events to reconstruct Shortfall state.

The Shortfall aggregate is terminal at genesis: `ShortfallRecorded` is
the only event type, and the only state-producing arm. A capture that
is later ingested by hand is NOT a correction to this fact and emits no
event here; both facts stand (see `Shortfall`'s module docstring), so
there is no transition arm and no retraction arm.

Same single-arm shape as the Acquisition and Decision evolvers. The
terminal `assert_never` forces pyright (and the runtime) to error if a
new event type is ever added to `ShortfallEvent` without a matching arm
here.

The genesis arm ignores prior state: a duplicate genesis on the same
stream is prevented at append time by `expected_version=0`, not here.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.data.aggregates.shortfall.events import ShortfallEvent, ShortfallRecorded
from cora.data.aggregates.shortfall.state import Shortfall, ShortfallStatus


def evolve(state: Shortfall | None, event: ShortfallEvent) -> Shortfall:
    """Apply one event to the current state."""
    match event:
        case ShortfallRecorded(
            shortfall_id=shortfall_id,
            producing_run_id=producing_run_id,
            capture_path_id=capture_path_id,
            host=host,
            root=root,
            projection_count=projection_count,
            commanded_projection_count=commanded_projection_count,
            dropped_frame_count=dropped_frame_count,
            reason=reason,
            file_modified_at=file_modified_at,
            run_ended_at=run_ended_at,
            occurred_at=occurred_at,
            recorded_by=recorded_by,
        ):
            _ = state  # ShortfallRecorded is the genesis event; prior state ignored.
            return Shortfall(
                id=shortfall_id,
                producing_run_id=producing_run_id,
                capture_path_id=capture_path_id,
                host=host,
                root=root,
                projection_count=projection_count,
                commanded_projection_count=commanded_projection_count,
                dropped_frame_count=dropped_frame_count,
                reason=reason,
                file_modified_at=file_modified_at,
                run_ended_at=run_ended_at,
                recorded_at=occurred_at,
                recorded_by=recorded_by,
                status=ShortfallStatus.RECORDED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ShortfallEvent]) -> Shortfall | None:
    """Replay a stream of events from the empty initial state."""
    state: Shortfall | None = None
    for event in events:
        state = evolve(state, event)
    return state
