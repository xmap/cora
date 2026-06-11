"""Evolver: replay events to reconstruct Acquisition state.

The Acquisition aggregate is terminal at genesis: `AcquisitionRecorded`
is the only event type, and the only state-producing arm. A flawed
capture is corrected by recording a NEW Acquisition (its own stream),
never by mutating an existing one, so there is no transition arm.

Same single-arm shape as the Decision aggregate's genesis-only
evolver. The terminal `assert_never` forces pyright (and the runtime)
to error if a new event type is ever added to `AcquisitionEvent`
without a matching arm here.

The genesis arm ignores prior state: a duplicate genesis on the same
stream is prevented at append time by `expected_version=0`
(`AcquisitionAlreadyExistsError` at the handler), not here.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.data.aggregates.acquisition.events import (
    AcquisitionEvent,
    AcquisitionRecorded,
)
from cora.data.aggregates.acquisition.state import Acquisition, AcquisitionStatus


def evolve(state: Acquisition | None, event: AcquisitionEvent) -> Acquisition:
    """Apply one event to the current state."""
    match event:
        case AcquisitionRecorded(
            acquisition_id=acquisition_id,
            dataset_id=dataset_id,
            producing_asset_id=producing_asset_id,
            producing_run_id=producing_run_id,
            captured_at=captured_at,
            settings=settings,
            evidence=evidence,
            occurred_at=occurred_at,
            recorded_by=recorded_by,
        ):
            _ = state  # AcquisitionRecorded is the genesis event; prior state ignored.
            return Acquisition(
                id=acquisition_id,
                dataset_id=dataset_id,
                producing_asset_id=producing_asset_id,
                producing_run_id=producing_run_id,
                captured_at=captured_at,
                # Defensive copies so mutating either side cannot alias.
                settings=dict(settings),
                evidence=dict(evidence),
                recorded_at=occurred_at,
                recorded_by=recorded_by,
                status=AcquisitionStatus.RECORDED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AcquisitionEvent]) -> Acquisition | None:
    """Replay a stream of events from the empty initial state."""
    state: Acquisition | None = None
    for event in events:
        state = evolve(state, event)
    return state
