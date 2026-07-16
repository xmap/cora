"""Property-based tests for `seal_allocation.decide` (budget BC).

Complements the example-based `test_seal_allocation_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, *, now, spent_usd, sealed_by) -> list[AllocationSealed]

Load-bearing properties:

  - state=None always raises `AllocationNotFoundError` carrying
    command.allocation_id.
  - The source-state partition is total over `AllocationStatus`:
    only `Active` emits exactly one `AllocationSealed`; every other
    status raises `AllocationCannotSealError` carrying the current
    status.
  - The snapshot passes through verbatim: for any finite non-negative
    `spent_usd` the emitted event carries exactly the reader's value
    (the closing-the-books figure is never recomputed or rounded
    here).
  - The emitted event's allocation_id is `state.id`, never
    `command.allocation_id`.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.budget.aggregates.allocation import (
    AllocationCannotSealError,
    AllocationNotFoundError,
    AllocationSealed,
    AllocationStatus,
)
from cora.budget.features.seal_allocation.command import SealAllocation
from cora.budget.features.seal_allocation.decider import decide
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes
from tests.unit.budget._helpers import make_allocation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_SEALABLE_SOURCES = (AllocationStatus.ACTIVE,)
_DISALLOWED_SOURCES = tuple(s for s in AllocationStatus if s not in frozenset(_SEALABLE_SOURCES))

_spend_snapshots = st.floats(
    min_value=0.0,
    max_value=1e12,
    allow_nan=False,
    allow_infinity=False,
)


@pytest.mark.unit
@given(
    allocation_id=st.uuids(),
    spent_usd=_spend_snapshots,
    sealed_by=st.uuids(),
    now=aware_datetimes(),
)
def test_seal_with_none_state_always_raises_not_found(
    allocation_id: UUID,
    spent_usd: float,
    sealed_by: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises not-found carrying command.allocation_id."""
    with pytest.raises(AllocationNotFoundError) as exc:
        decide(
            state=None,
            command=SealAllocation(allocation_id=allocation_id),
            now=now,
            spent_usd=spent_usd,
            sealed_by=ActorId(sealed_by),
        )
    assert exc.value.allocation_id == allocation_id


@pytest.mark.unit
@given(
    allocation_id=st.uuids(),
    spent_usd=_spend_snapshots,
    sealed_by=st.uuids(),
    now=aware_datetimes(),
)
def test_seal_from_active_records_readers_value_verbatim(
    allocation_id: UUID,
    spent_usd: float,
    sealed_by: UUID,
    now: datetime,
) -> None:
    """Active is the only sealable source; the snapshot is the reader's
    value, untouched."""
    events = decide(
        state=make_allocation(AllocationStatus.ACTIVE, allocation_id=allocation_id),
        command=SealAllocation(allocation_id=allocation_id),
        now=now,
        spent_usd=spent_usd,
        sealed_by=ActorId(sealed_by),
    )
    assert events == [
        AllocationSealed(
            allocation_id=allocation_id,
            spent_usd=spent_usd,
            reason=None,
            sealed_by=ActorId(sealed_by),
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    allocation_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    spent_usd=_spend_snapshots,
    sealed_by=st.uuids(),
    now=aware_datetimes(),
)
def test_seal_from_disallowed_source_always_raises_cannot_seal(
    allocation_id: UUID,
    source: AllocationStatus,
    spent_usd: float,
    sealed_by: UUID,
    now: datetime,
) -> None:
    """Any source other than Active raises, carrying the current status."""
    with pytest.raises(AllocationCannotSealError) as exc:
        decide(
            state=make_allocation(source, allocation_id=allocation_id),
            command=SealAllocation(allocation_id=allocation_id),
            now=now,
            spent_usd=spent_usd,
            sealed_by=ActorId(sealed_by),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), sealed_by=st.uuids(), now=aware_datetimes())
def test_seal_uses_state_id_not_command_allocation_id(
    state_id: UUID,
    command_id: UUID,
    sealed_by: UUID,
    now: datetime,
) -> None:
    """The emitted event's allocation_id is state.id, not command's."""
    assume(state_id != command_id)
    events = decide(
        state=make_allocation(AllocationStatus.ACTIVE, allocation_id=state_id),
        command=SealAllocation(allocation_id=command_id),
        now=now,
        spent_usd=0.0,
        sealed_by=ActorId(sealed_by),
    )
    assert events[0].allocation_id == state_id


@pytest.mark.unit
@given(spent_usd=_spend_snapshots, sealed_by=st.uuids(), now=aware_datetimes())
def test_seal_is_pure_same_input_same_output(
    spent_usd: float,
    sealed_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    envelope = make_allocation(AllocationStatus.ACTIVE)
    command = SealAllocation(allocation_id=envelope.id)
    first = decide(
        state=envelope, command=command, now=now, spent_usd=spent_usd, sealed_by=ActorId(sealed_by)
    )
    second = decide(
        state=envelope, command=command, now=now, spent_usd=spent_usd, sealed_by=ActorId(sealed_by)
    )
    assert first == second
