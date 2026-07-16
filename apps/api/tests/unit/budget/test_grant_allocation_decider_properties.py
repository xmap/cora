"""Property-based tests for `grant_allocation.decide` (budget BC).

Complements the example-based `test_grant_allocation_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, *, now, new_id, granted_by) -> list[AllocationGranted]

Load-bearing properties:

  - Any non-None state always raises `AllocationAlreadyExistsError`
    carrying state.id, regardless of command.
  - The ceiling partition is total over floats: finite positive
    ceilings emit exactly one event carrying them verbatim; zero,
    negative, and non-finite ceilings always raise
    `InvalidAllocationCeilingError` (one bad ceiling would arm or
    disarm the envelope check unconditionally).
  - The emitted event carries the injected now / new_id / granted_by.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.budget.aggregates.allocation import (
    AllocationAlreadyExistsError,
    AllocationStatus,
    InvalidAllocationCeilingError,
)
from cora.budget.features.grant_allocation.command import GrantAllocation
from cora.budget.features.grant_allocation.decider import decide
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text
from tests.unit.budget._helpers import make_allocation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

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
@given(
    state_id=st.uuids(),
    status=st.sampled_from(list(AllocationStatus)),
    new_id=st.uuids(),
    granted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_grant_with_any_existing_state_always_raises_already_exists(
    state_id: UUID,
    status: AllocationStatus,
    new_id: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """Genesis-only: any prior state (any status) refuses, carrying state.id."""
    with pytest.raises(AllocationAlreadyExistsError) as exc:
        decide(
            state=make_allocation(status, allocation_id=state_id),
            command=GrantAllocation(ceiling_usd=100.0, note="Envelope"),
            now=now,
            new_id=new_id,
            granted_by=ActorId(granted_by),
        )
    assert exc.value.allocation_id == state_id


@pytest.mark.unit
@given(
    ceiling=_valid_ceilings,
    note=printable_ascii_text(max_size=200),
    new_id=st.uuids(),
    granted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_grant_happy_path_emits_single_event_with_injected_fields(
    ceiling: float,
    note: str,
    new_id: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """Any finite positive ceiling grants; the event carries the inputs verbatim."""
    events = decide(
        state=None,
        command=GrantAllocation(ceiling_usd=ceiling, note=note),
        now=now,
        new_id=new_id,
        granted_by=ActorId(granted_by),
    )
    assert len(events) == 1
    event = events[0]
    assert event.allocation_id == new_id
    assert event.ceiling_usd == ceiling
    assert event.note == note
    assert event.granted_by == ActorId(granted_by)
    assert event.occurred_at == now
    assert event.campaign_id is None


@pytest.mark.unit
@given(
    ceiling=_invalid_ceilings,
    new_id=st.uuids(),
    granted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_grant_non_positive_or_non_finite_ceiling_always_raises(
    ceiling: float,
    new_id: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """The ceiling partition is total: everything outside finite-positive raises."""
    assert not (isfinite(ceiling) and ceiling > 0.0)
    with pytest.raises(InvalidAllocationCeilingError):
        decide(
            state=None,
            command=GrantAllocation(ceiling_usd=ceiling, note="Envelope"),
            now=now,
            new_id=new_id,
            granted_by=ActorId(granted_by),
        )


@pytest.mark.unit
@given(
    ceiling=_valid_ceilings,
    new_id=st.uuids(),
    granted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_grant_is_pure_same_input_same_output(
    ceiling: float,
    new_id: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    command = GrantAllocation(ceiling_usd=ceiling, note="Envelope")
    first = decide(
        state=None, command=command, now=now, new_id=new_id, granted_by=ActorId(granted_by)
    )
    second = decide(
        state=None, command=command, now=now, new_id=new_id, granted_by=ActorId(granted_by)
    )
    assert first == second
