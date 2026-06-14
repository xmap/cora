"""Property-based tests for `register_enclosure.decide` (Enclosure BC).

Mirrors the Access / Trust / Federation / Supply decider-PBT pattern.
Universal claims across generated inputs:

  - state=None + valid command emits a single EnclosureRegistered with
    the injected enclosure_id / now / registered_by and the command's
    name / facility_code.
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
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID


_DISPLAY_NAME = printable_ascii_text(min_size=1, max_size=200)
# Cross-deployment convergent slugs: lowercase ASCII alphanumeric + dash, 1-32.
_FACILITY_CODE = st.from_regex(r"^[a-z0-9-]{1,32}$", fullmatch=True)


def _facility_result(code: str) -> FacilityLookupResult:
    from uuid import uuid4

    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(),
    )


def _command(*, name: str = "2-BM Hutch A", facility_code: str = "aps") -> RegisterEnclosure:
    return RegisterEnclosure(name=name, facility_code=facility_code)


def _existing_state(enclosure_id: UUID, facility_code: str, actor_id: UUID) -> Enclosure:
    return Enclosure(
        id=EnclosureId(enclosure_id),
        name=EnclosureName("2-BM Hutch A"),
        facility_code=FacilityCode(facility_code),
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
    facility_code=_FACILITY_CODE,
    actor_id=st.uuids(),
)
def test_register_enclosure_genesis_emits_single_event_with_injected_fields(
    display_name: str,
    now: datetime,
    enclosure_id: UUID,
    facility_code: str,
    actor_id: UUID,
) -> None:
    """Empty stream + valid command emits a single EnclosureRegistered."""
    command = _command(name=display_name, facility_code=facility_code)
    events = register_enclosure.decide(
        state=None,
        command=command,
        now=now,
        new_id=EnclosureId(enclosure_id),
        registered_by=ActorId(actor_id),
        facility_lookup_result=_facility_result(facility_code),
    )
    assert len(events) == 1
    event = events[0]
    assert event.enclosure_id == enclosure_id
    assert event.name == display_name
    assert event.facility_code == FacilityCode(facility_code)
    assert event.registered_by == actor_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    existing_enclosure_id=st.uuids(),
    new_enclosure_id=st.uuids(),
    facility_code=_FACILITY_CODE,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_register_enclosure_on_existing_state_always_raises_already_exists(
    existing_enclosure_id: UUID,
    new_enclosure_id: UUID,
    facility_code: str,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Any non-None state raises EnclosureAlreadyExistsError."""
    with pytest.raises(EnclosureAlreadyExistsError) as exc:
        register_enclosure.decide(
            state=_existing_state(existing_enclosure_id, facility_code, actor_id),
            command=_command(facility_code=facility_code),
            now=now,
            new_id=EnclosureId(new_enclosure_id),
            registered_by=ActorId(actor_id),
            facility_lookup_result=_facility_result(facility_code),
        )
    assert exc.value.enclosure_id == existing_enclosure_id


@pytest.mark.unit
@given(
    display_name=_DISPLAY_NAME,
    now=aware_datetimes(),
    enclosure_id=st.uuids(),
    facility_code=_FACILITY_CODE,
    actor_id=st.uuids(),
)
def test_register_enclosure_is_pure_same_input_same_output(
    display_name: str,
    now: datetime,
    enclosure_id: UUID,
    facility_code: str,
    actor_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = _command(name=display_name, facility_code=facility_code)
    lookup_result = _facility_result(facility_code)
    first = register_enclosure.decide(
        state=None,
        command=command,
        now=now,
        new_id=EnclosureId(enclosure_id),
        registered_by=ActorId(actor_id),
        facility_lookup_result=lookup_result,
    )
    second = register_enclosure.decide(
        state=None,
        command=command,
        now=now,
        new_id=EnclosureId(enclosure_id),
        registered_by=ActorId(actor_id),
        facility_lookup_result=lookup_result,
    )
    assert first == second
