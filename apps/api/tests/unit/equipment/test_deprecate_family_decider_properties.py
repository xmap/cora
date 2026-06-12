"""Property-based tests for `deprecate_family.decide` (Equipment BC).

Complements the example-based `test_deprecate_family_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM terminal

    (state, command, now) -> list[FamilyDeprecated]

Load-bearing properties:

  - state=None always raises `FamilyNotFoundError` carrying
    command.family_id.
  - The source-state partition is total over `FamilyStatus`: only
    `Defined` and `Versioned` emit exactly one `FamilyDeprecated`
    (family_id=state.id, occurred_at=now); every other status raises
    `FamilyCannotDeprecateError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's family_id is `state.id`, never command.family_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.family import (
    Family,
    FamilyCannotDeprecateError,
    FamilyDeprecated,
    FamilyName,
    FamilyNotFoundError,
    FamilyStatus,
)
from cora.equipment.features import deprecate_family
from cora.equipment.features.deprecate_family import DeprecateFamily
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_DEPRECATABLE_SOURCES = (FamilyStatus.DEFINED, FamilyStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in FamilyStatus if s not in frozenset(_DEPRECATABLE_SOURCES))


def _family(*, family_id: UUID, status: FamilyStatus) -> Family:
    return Family(
        id=family_id,
        name=FamilyName("Tomography"),
        status=status,
        version=None,
    )


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_deprecate_with_none_state_always_raises_not_found(
    family_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `FamilyNotFoundError` carrying the id."""
    with pytest.raises(FamilyNotFoundError) as exc:
        deprecate_family.decide(
            state=None,
            command=DeprecateFamily(family_id=family_id),
            now=now,
        )
    assert exc.value.family_id == family_id


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_allowed_source_emits_single_event(
    family_id: UUID,
    source: FamilyStatus,
    now: datetime,
) -> None:
    """Each deprecatable source emits exactly one FamilyDeprecated."""
    events = deprecate_family.decide(
        state=_family(family_id=family_id, status=source),
        command=DeprecateFamily(family_id=family_id),
        now=now,
    )
    assert events == [FamilyDeprecated(family_id=family_id, occurred_at=now)]


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_disallowed_source_always_raises_cannot_deprecate(
    family_id: UUID,
    source: FamilyStatus,
    now: datetime,
) -> None:
    """Any source outside the allowed set raises, carrying the status."""
    with pytest.raises(FamilyCannotDeprecateError) as exc:
        deprecate_family.decide(
            state=_family(family_id=family_id, status=source),
            command=DeprecateFamily(family_id=family_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_deprecate_emits_event_with_state_id_not_command_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's family_id is state.id, not command.family_id."""
    assume(state_id != command_id)
    events = deprecate_family.decide(
        state=_family(family_id=state_id, status=FamilyStatus.DEFINED),
        command=DeprecateFamily(family_id=command_id),
        now=now,
    )
    assert events[0].family_id == state_id


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_deprecate_is_pure_same_input_same_output(
    family_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leak)."""
    state = _family(family_id=family_id, status=FamilyStatus.DEFINED)
    command = DeprecateFamily(family_id=family_id)
    first = deprecate_family.decide(state=state, command=command, now=now)
    second = deprecate_family.decide(state=state, command=command, now=now)
    assert first == second
