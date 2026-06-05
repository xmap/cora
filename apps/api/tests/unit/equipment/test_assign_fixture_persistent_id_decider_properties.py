"""Property-based tests for `assign_fixture_persistent_id.decide`.

Required PBT per the `test_decider_changes_require_paired_pbt`
architecture fitness. Mirrors the sibling
`test_assign_asset_persistent_id_decider_properties.py` shape:
Hypothesis strategies generate `(scheme, value)` pairs spanning the
full closed `PersistentIdentifierScheme` enum, plus prior-state
variants (absent vs already-assigned). Fixture has no lifecycle FSM
today, so there is no lifecycle-forbidden property here.

Properties asserted (per memo section 15.2):
  - assign_with_valid_inputs_emits_one_event: purity + single-event
    invariant on the happy path
  - assign_with_state_persistent_id_set_always_raises_already_assigned:
    set-once per Section 2.3
  - emitted_event_scheme_and_value_match_resolved_persistent_id:
    event-shape invariant per L11
  - decider_deterministic_given_state_and_args: purity (no clock,
    no minter)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.equipment.aggregates.fixture import (
    Fixture,
    FixturePersistentIdAlreadyAssignedError,
    FixturePersistentIdAssigned,
)
from cora.equipment.features import assign_fixture_persistent_id
from cora.equipment.features.assign_fixture_persistent_id.command import (
    AssignFixturePersistentId,
)

if TYPE_CHECKING:
    from uuid import UUID

pytestmark = pytest.mark.timeout(60, method="thread")

_SCHEME = st.sampled_from(list(PersistentIdentifierScheme))
_VALID_VALUE = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
)
_DT_BASE = datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)


@st.composite
def _persistent_identifier(draw: st.DrawFn) -> PersistentIdentifier:
    return PersistentIdentifier(scheme=draw(_SCHEME), value=draw(_VALID_VALUE))


def _fixture(
    fixture_id: UUID,
    *,
    persistent_id: PersistentIdentifier | None,
) -> Fixture:
    return Fixture(
        id=fixture_id,
        assembly_id=uuid4(),
        assembly_content_hash="a" * 64,
        surface_id=uuid4(),
        registered_at=_DT_BASE,
        persistent_id=persistent_id,
    )


@pytest.mark.unit
@given(
    fixture_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_assign_with_valid_inputs_emits_one_event(
    fixture_id: UUID,
    persistent_id: PersistentIdentifier,
    seconds_offset: int,
) -> None:
    state = _fixture(fixture_id, persistent_id=None)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignFixturePersistentId(
        fixture_id=fixture_id,
        scheme=persistent_id.scheme,
    )
    events = assign_fixture_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    assert events == [
        FixturePersistentIdAssigned(
            fixture_id=fixture_id,
            persistent_id_scheme=persistent_id.scheme.value,
            persistent_id_value=persistent_id.value,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    fixture_id=st.uuids(),
    current=_persistent_identifier(),
    attempted=_persistent_identifier(),
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_assign_with_state_persistent_id_set_always_raises_already_assigned(
    fixture_id: UUID,
    current: PersistentIdentifier,
    attempted: PersistentIdentifier,
    seconds_offset: int,
) -> None:
    state = _fixture(fixture_id, persistent_id=current)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignFixturePersistentId(
        fixture_id=fixture_id,
        scheme=attempted.scheme,
    )
    with pytest.raises(FixturePersistentIdAlreadyAssignedError) as exc:
        assign_fixture_persistent_id.decide(
            state,
            command,
            persistent_id=attempted,
            now=now,
        )
    assert exc.value.fixture_id == fixture_id
    assert exc.value.current == current
    assert exc.value.attempted == attempted


@pytest.mark.unit
@given(
    fixture_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_emitted_event_scheme_and_value_match_resolved_persistent_id(
    fixture_id: UUID,
    persistent_id: PersistentIdentifier,
    seconds_offset: int,
) -> None:
    state = _fixture(fixture_id, persistent_id=None)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignFixturePersistentId(
        fixture_id=fixture_id,
        scheme=persistent_id.scheme,
    )
    events = assign_fixture_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FixturePersistentIdAssigned)
    assert event.persistent_id_scheme == persistent_id.scheme.value
    assert event.persistent_id_value == persistent_id.value
    assert event.fixture_id == fixture_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    fixture_id=st.uuids(),
    persistent_id=_persistent_identifier(),
    other=_persistent_identifier(),
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_decider_is_deterministic_given_state_and_args(
    fixture_id: UUID,
    persistent_id: PersistentIdentifier,
    other: PersistentIdentifier,
    seconds_offset: int,
) -> None:
    assume(persistent_id != other)
    state = _fixture(fixture_id, persistent_id=None)
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AssignFixturePersistentId(
        fixture_id=fixture_id,
        scheme=persistent_id.scheme,
    )
    first = assign_fixture_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    second = assign_fixture_persistent_id.decide(
        state,
        command,
        persistent_id=persistent_id,
        now=now,
    )
    assert first == second
