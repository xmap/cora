"""Property-based tests for `update_allocation_ceiling.decide` (budget BC).

Complements the example-based `test_update_allocation_ceiling_decider.py`
with universal claims across generated inputs. The decider is a pure
PUT-semantics update

    (state, command, *, now) -> list[AllocationCeilingUpdated]

Load-bearing properties:

  - state=None always raises `AllocationNotFoundError` carrying
    command.allocation_id.
  - The source-state partition is total over `AllocationStatus`:
    Granted and Active accept; Sealed and Voided always raise
    `AllocationCannotUpdateCeilingError` carrying the current status.
  - PUT idempotency: updating to the stored ceiling returns [] for
    every valid ceiling; updating to a different valid ceiling emits
    exactly one event carrying it verbatim with state.id.
  - Invalid ceilings (non-positive or non-finite) always raise from
    an updatable source, regardless of the stored value.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.budget.aggregates.allocation import (
    AllocationCannotUpdateCeilingError,
    AllocationCeilingUpdated,
    AllocationNotFoundError,
    AllocationStatus,
    InvalidAllocationCeilingError,
)
from cora.budget.features.update_allocation_ceiling.command import UpdateAllocationCeiling
from cora.budget.features.update_allocation_ceiling.decider import decide
from tests._strategies import aware_datetimes
from tests.unit.budget._helpers import make_allocation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_UPDATABLE_SOURCES = (AllocationStatus.GRANTED, AllocationStatus.ACTIVE)
_DISALLOWED_SOURCES = tuple(s for s in AllocationStatus if s not in frozenset(_UPDATABLE_SOURCES))

_valid_ceilings = st.floats(
    min_value=0.01,
    max_value=1e12,
    allow_nan=False,
    allow_infinity=False,
)
_invalid_ceilings = st.one_of(
    st.floats(max_value=0.0, allow_nan=False),
    st.just(float("nan")),
    st.just(float("inf")),
    st.just(float("-inf")),
)


@pytest.mark.unit
@given(allocation_id=st.uuids(), ceiling=_valid_ceilings, now=aware_datetimes())
def test_update_with_none_state_always_raises_not_found(
    allocation_id: UUID,
    ceiling: float,
    now: datetime,
) -> None:
    """Empty stream always raises not-found carrying command.allocation_id."""
    with pytest.raises(AllocationNotFoundError) as exc:
        decide(
            state=None,
            command=UpdateAllocationCeiling(allocation_id=allocation_id, ceiling_usd=ceiling),
            now=now,
        )
    assert exc.value.allocation_id == allocation_id


@pytest.mark.unit
@given(
    allocation_id=st.uuids(),
    source=st.sampled_from(_UPDATABLE_SOURCES),
    stored=_valid_ceilings,
    updated=_valid_ceilings,
    now=aware_datetimes(),
)
def test_update_to_different_ceiling_emits_single_event_with_state_id(
    allocation_id: UUID,
    source: AllocationStatus,
    stored: float,
    updated: float,
    now: datetime,
) -> None:
    """From an updatable source, a differing valid ceiling emits ONE event
    carrying the updated value verbatim."""
    assume(stored != updated)
    events = decide(
        state=make_allocation(source, allocation_id=allocation_id, ceiling_usd=stored),
        command=UpdateAllocationCeiling(allocation_id=allocation_id, ceiling_usd=updated),
        now=now,
    )
    assert events == [
        AllocationCeilingUpdated(allocation_id=allocation_id, ceiling_usd=updated, occurred_at=now)
    ]


@pytest.mark.unit
@given(
    source=st.sampled_from(_UPDATABLE_SOURCES),
    ceiling=_valid_ceilings,
    now=aware_datetimes(),
)
def test_update_to_stored_ceiling_always_returns_no_events(
    source: AllocationStatus,
    ceiling: float,
    now: datetime,
) -> None:
    """PUT idempotency holds for every valid ceiling value."""
    envelope = make_allocation(source, ceiling_usd=ceiling)
    events = decide(
        state=envelope,
        command=UpdateAllocationCeiling(allocation_id=envelope.id, ceiling_usd=ceiling),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    source=st.sampled_from(_DISALLOWED_SOURCES),
    ceiling=_valid_ceilings,
    now=aware_datetimes(),
)
def test_update_from_terminal_source_always_raises_cannot_update(
    source: AllocationStatus,
    ceiling: float,
    now: datetime,
) -> None:
    """Sealed and Voided books cannot be rewritten; carries the current status."""
    envelope = make_allocation(source)
    with pytest.raises(AllocationCannotUpdateCeilingError) as exc:
        decide(
            state=envelope,
            command=UpdateAllocationCeiling(allocation_id=envelope.id, ceiling_usd=ceiling),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    source=st.sampled_from(_UPDATABLE_SOURCES),
    ceiling=_invalid_ceilings,
    now=aware_datetimes(),
)
def test_update_invalid_ceiling_always_raises(
    source: AllocationStatus,
    ceiling: float,
    now: datetime,
) -> None:
    """The ceiling partition is total: everything outside finite-positive raises."""
    assert not (isfinite(ceiling) and ceiling > 0.0)
    envelope = make_allocation(source)
    with pytest.raises(InvalidAllocationCeilingError):
        decide(
            state=envelope,
            command=UpdateAllocationCeiling(allocation_id=envelope.id, ceiling_usd=ceiling),
            now=now,
        )


@pytest.mark.unit
@given(ceiling=_valid_ceilings, now=aware_datetimes())
def test_update_is_pure_same_input_same_output(ceiling: float, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    envelope = make_allocation(AllocationStatus.ACTIVE, ceiling_usd=123.45)
    command = UpdateAllocationCeiling(allocation_id=envelope.id, ceiling_usd=ceiling)
    first = decide(state=envelope, command=command, now=now)
    second = decide(state=envelope, command=command, now=now)
    assert first == second
