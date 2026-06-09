"""Property-based tests for `register_enclosure.decide` (Enclosure BC).

Mirrors the Access / Trust / Federation / Supply decider-PBT pattern.
Universal claims across generated inputs:

  - state=None + valid command emits a single EnclosureRegistered with
    the injected enclosure_id / now / registered_by and the command's
    name / containing_asset_id.
  - state=Enclosure always raises EnclosureAlreadyExistsError,
    regardless of command shape.
  - Pure: same (state, command, now, new_id, registered_by) returns
    the same events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureAlreadyExistsError,
    EnclosureLifecycle,
    EnclosureName,
    EnclosurePermitStatus,
)
from cora.enclosure.features import register_enclosure
from cora.enclosure.features.register_enclosure import RegisterEnclosure
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID


_DISPLAY_NAME = printable_ascii_text(min_size=1, max_size=200)


def _command(
    *, name: str = "2-BM Hutch A", containing_asset_id: UUID | None = None
) -> RegisterEnclosure:
    from uuid import uuid4

    return RegisterEnclosure(
        name=name,
        containing_asset_id=containing_asset_id if containing_asset_id is not None else uuid4(),
    )


def _existing_state(enclosure_id: UUID, containing_asset_id: UUID, actor_id: UUID) -> Enclosure:
    return Enclosure(
        id=EnclosureId(enclosure_id),
        name=EnclosureName("2-BM Hutch A"),
        containing_asset_id=containing_asset_id,
        permit_status=EnclosurePermitStatus.UNKNOWN,
        lifecycle=EnclosureLifecycle.ACTIVE,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
        registered_by=ActorId(actor_id),
        decommissioned_at=None,
        decommissioned_by=None,
    )


@pytest.mark.unit
@given(
    display_name=_DISPLAY_NAME,
    now=aware_datetimes(),
    enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    actor_id=st.uuids(),
)
def test_register_enclosure_genesis_emits_single_event_with_injected_fields(
    display_name: str,
    now: datetime,
    enclosure_id: UUID,
    containing_asset_id: UUID,
    actor_id: UUID,
) -> None:
    """Empty stream + valid command emits a single EnclosureRegistered."""
    command = _command(name=display_name, containing_asset_id=containing_asset_id)
    events = register_enclosure.decide(
        state=None,
        command=command,
        now=now,
        new_id=EnclosureId(enclosure_id),
        registered_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.enclosure_id == enclosure_id
    assert event.name == display_name
    assert event.containing_asset_id == containing_asset_id
    assert event.registered_by == actor_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    existing_enclosure_id=st.uuids(),
    new_enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_register_enclosure_on_existing_state_always_raises_already_exists(
    existing_enclosure_id: UUID,
    new_enclosure_id: UUID,
    containing_asset_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Any non-None state raises EnclosureAlreadyExistsError."""
    with pytest.raises(EnclosureAlreadyExistsError) as exc:
        register_enclosure.decide(
            state=_existing_state(existing_enclosure_id, containing_asset_id, actor_id),
            command=_command(containing_asset_id=containing_asset_id),
            now=now,
            new_id=EnclosureId(new_enclosure_id),
            registered_by=ActorId(actor_id),
        )
    assert exc.value.enclosure_id == existing_enclosure_id


@pytest.mark.unit
@given(
    display_name=_DISPLAY_NAME,
    now=aware_datetimes(),
    enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    actor_id=st.uuids(),
)
def test_register_enclosure_is_pure_same_input_same_output(
    display_name: str,
    now: datetime,
    enclosure_id: UUID,
    containing_asset_id: UUID,
    actor_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = _command(name=display_name, containing_asset_id=containing_asset_id)
    first = register_enclosure.decide(
        state=None,
        command=command,
        now=now,
        new_id=EnclosureId(enclosure_id),
        registered_by=ActorId(actor_id),
    )
    second = register_enclosure.decide(
        state=None,
        command=command,
        now=now,
        new_id=EnclosureId(enclosure_id),
        registered_by=ActorId(actor_id),
    )
    assert first == second
