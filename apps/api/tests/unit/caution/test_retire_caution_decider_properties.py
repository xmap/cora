"""Property-based tests for `retire_caution.decide` (Caution BC).

Complements the example-based `test_retire_caution_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source terminal transition with a closed-enum reason

    (state, command, now) -> list[CautionRetired]

Load-bearing properties:

  - state=None always raises `CautionNotFoundError` carrying
    command.caution_id.
  - The source-state partition is total over `CautionStatus`: only
    `Active` emits exactly one `CautionRetired` (caution_id=state.id,
    reason threaded, occurred_at=now); every other status raises
    `CautionCannotRetireError` carrying the current status.
  - The emitted event's caution_id is `state.id`, never
    command.caution_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.caution.aggregates.caution import (
    AssetTarget,
    Caution,
    CautionCannotRetireError,
    CautionCategory,
    CautionNotFoundError,
    CautionRetired,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
    CautionText,
    CautionWorkaround,
)
from cora.caution.features import retire_caution
from cora.caution.features.retire_caution import RetireCaution
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_REASON = st.sampled_from(list(CautionRetireReason))
_RETIRABLE_SOURCES = (CautionStatus.ACTIVE,)
_DISALLOWED_SOURCES = tuple(s for s in CautionStatus if s not in frozenset(_RETIRABLE_SOURCES))


def _caution(*, caution_id: UUID, status: CautionStatus) -> Caution:
    return Caution(
        id=caution_id,
        target=AssetTarget(asset_id=UUID(int=8)),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.NOTICE,
        text=CautionText("hexapod stalls below 0.5 mm/s"),
        workaround=CautionWorkaround("ramp velocity above 0.5 before homing"),
        authored_by=ActorId(UUID(int=9)),
        status=status,
    )


@pytest.mark.unit
@given(caution_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_retire_with_none_state_always_raises_not_found(
    caution_id: UUID,
    reason: CautionRetireReason,
    now: datetime,
) -> None:
    """Empty stream always raises `CautionNotFoundError` carrying command.caution_id."""
    with pytest.raises(CautionNotFoundError) as exc:
        retire_caution.decide(
            state=None,
            command=RetireCaution(caution_id=caution_id, reason=reason),
            now=now,
        )
    assert exc.value.caution_id == caution_id


@pytest.mark.unit
@given(caution_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_retire_from_active_emits_single_event(
    caution_id: UUID,
    reason: CautionRetireReason,
    now: datetime,
) -> None:
    """Active is the only retirable source; emits one CautionRetired with the reason."""
    events = retire_caution.decide(
        state=_caution(caution_id=caution_id, status=CautionStatus.ACTIVE),
        command=RetireCaution(caution_id=caution_id, reason=reason),
        now=now,
    )
    assert events == [CautionRetired(caution_id=caution_id, reason=reason.value, occurred_at=now)]


@pytest.mark.unit
@given(
    caution_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_retire_from_disallowed_source_always_raises_cannot_retire(
    caution_id: UUID,
    source: CautionStatus,
    reason: CautionRetireReason,
    now: datetime,
) -> None:
    """Any source other than Active raises, carrying the current status."""
    with pytest.raises(CautionCannotRetireError) as exc:
        retire_caution.decide(
            state=_caution(caution_id=caution_id, status=source),
            command=RetireCaution(caution_id=caution_id, reason=reason),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_caution_id=st.uuids(),
    command_caution_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_retire_uses_state_id_not_command_caution_id(
    state_caution_id: UUID,
    command_caution_id: UUID,
    reason: CautionRetireReason,
    now: datetime,
) -> None:
    """The emitted event's caution_id is state.id, not command.caution_id."""
    assume(state_caution_id != command_caution_id)
    events = retire_caution.decide(
        state=_caution(caution_id=state_caution_id, status=CautionStatus.ACTIVE),
        command=RetireCaution(caution_id=command_caution_id, reason=reason),
        now=now,
    )
    assert events[0].caution_id == state_caution_id


@pytest.mark.unit
@given(caution_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_retire_is_pure_same_input_same_output(
    caution_id: UUID,
    reason: CautionRetireReason,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _caution(caution_id=caution_id, status=CautionStatus.ACTIVE)
    command = RetireCaution(caution_id=caution_id, reason=reason)
    first = retire_caution.decide(state=state, command=command, now=now)
    second = retire_caution.decide(state=state, command=command, now=now)
    assert first == second
