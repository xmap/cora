"""Property-based tests for `version_family.decide` (Equipment BC).

Complements the example-based `test_version_family_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition

    (state, command, now) -> list[FamilyVersioned]

Load-bearing properties:

  - state=None always raises `FamilyNotFoundError` carrying command.family_id.
  - The source-state partition is total over `FamilyStatus`: both
    `Defined` and `Versioned` emit exactly one `FamilyVersioned`
    (family_id=state.id, occurred_at=now); every other status raises
    `FamilyCannotVersionError` carrying the current status, so a future
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
    FamilyCannotVersionError,
    FamilyName,
    FamilyNotFoundError,
    FamilyStatus,
    FamilyVersioned,
)
from cora.equipment.features import version_family
from cora.equipment.features.version_family import VersionFamily
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_VERSION_TAG = "v2"

_VERSIONABLE_SOURCES = (FamilyStatus.DEFINED, FamilyStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in FamilyStatus if s not in frozenset(_VERSIONABLE_SOURCES))


def _family(*, family_id: UUID, status: FamilyStatus) -> Family:
    return Family(
        id=family_id,
        name=FamilyName("Tomography"),
        status=status,
    )


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_version_with_none_state_always_raises_not_found(
    family_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `FamilyNotFoundError` carrying command.family_id."""
    with pytest.raises(FamilyNotFoundError) as exc:
        version_family.decide(
            state=None,
            command=VersionFamily(
                family_id=family_id, version_tag=_VERSION_TAG, affordances=frozenset()
            ),
            now=now,
        )
    assert exc.value.family_id == family_id


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    source=st.sampled_from(_VERSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_allowed_source_emits_single_event(
    family_id: UUID,
    source: FamilyStatus,
    now: datetime,
) -> None:
    """Defined and Versioned both version; each emits one FamilyVersioned."""
    events = version_family.decide(
        state=_family(family_id=family_id, status=source),
        command=VersionFamily(
            family_id=family_id, version_tag=_VERSION_TAG, affordances=frozenset()
        ),
        now=now,
    )
    assert events == [
        FamilyVersioned(family_id=family_id, version_tag=_VERSION_TAG, occurred_at=now)
    ]


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_disallowed_source_always_raises_cannot_version(
    family_id: UUID,
    source: FamilyStatus,
    now: datetime,
) -> None:
    """Any source other than Defined or Versioned raises, carrying the current status."""
    with pytest.raises(FamilyCannotVersionError) as exc:
        version_family.decide(
            state=_family(family_id=family_id, status=source),
            command=VersionFamily(
                family_id=family_id, version_tag=_VERSION_TAG, affordances=frozenset()
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_family_id=st.uuids(), command_family_id=st.uuids(), now=aware_datetimes())
def test_version_emits_event_with_state_id_not_command_id(
    state_family_id: UUID,
    command_family_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's family_id is state.id, not command.family_id."""
    assume(state_family_id != command_family_id)
    events = version_family.decide(
        state=_family(family_id=state_family_id, status=FamilyStatus.DEFINED),
        command=VersionFamily(
            family_id=command_family_id, version_tag=_VERSION_TAG, affordances=frozenset()
        ),
        now=now,
    )
    assert events[0].family_id == state_family_id


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_version_emits_event_with_occurred_at_from_clock(
    family_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's occurred_at is the injected clock value."""
    events = version_family.decide(
        state=_family(family_id=family_id, status=FamilyStatus.DEFINED),
        command=VersionFamily(
            family_id=family_id, version_tag=_VERSION_TAG, affordances=frozenset()
        ),
        now=now,
    )
    assert events[0].occurred_at == now


@pytest.mark.unit
@given(family_id=st.uuids(), now=aware_datetimes())
def test_version_is_pure_same_input_same_output(family_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _family(family_id=family_id, status=FamilyStatus.DEFINED)
    command = VersionFamily(family_id=family_id, version_tag=_VERSION_TAG, affordances=frozenset())
    first = version_family.decide(state=state, command=command, now=now)
    second = version_family.decide(state=state, command=command, now=now)
    assert first == second
