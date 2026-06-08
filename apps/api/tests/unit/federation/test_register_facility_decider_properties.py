"""Property-based tests for `register_facility.decide` (Federation BC).

Mirrors the Access / Trust / Federation decider-PBT pattern. Universal
claims across generated inputs:

  - state=None + valid SITE command (parent_id=None) emits a single
    FacilityRegistered with the injected facility_id / code / now /
    registered_by and the command's display_name / kind.
  - state=None + valid AREA command (parent_id non-None) emits a single
    FacilityRegistered carrying the parent_id.
  - state=Facility always raises FacilityAlreadyExistsError, regardless
    of command shape.
  - kind=Site with non-None parent_id always raises
    FacilitySiteCannotHaveParentError.
  - kind=Area with None parent_id always raises
    FacilityAreaMustHaveParentError.
  - Pure: same (state, command, now, facility_id, code, registered_by)
    returns the same events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityAlreadyExistsError,
    FacilityAreaMustHaveParentError,
    FacilityKind,
    FacilityName,
    FacilitySiteCannotHaveParentError,
    FacilityStatus,
)
from cora.federation.features import register_facility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.ports import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID

# FacilityCode is alphanumeric+dash 1-32 chars; use a constant for the
# code parameter to keep the PBT focused on the structural invariants
# rather than the codepoint validator (covered by FacilityCode unit tests).
_CODE = FacilityCode("aps-site")
_AREA_CODE = FacilityCode("aps-area")
_DISPLAY_NAME = printable_ascii_text(min_size=1, max_size=200)


def _command(
    *,
    kind: FacilityKind,
    parent_id: FacilityId | None,
    display_name: str = "Advanced Photon Source",
    code: str = "aps-site",
) -> RegisterFacility:
    return RegisterFacility(
        code=code,
        display_name=display_name,
        kind=kind,
        parent_id=parent_id,
    )


def _existing_site_state(facility_id: UUID, actor_id: UUID) -> Facility:
    return Facility(
        id=FacilityId(facility_id),
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
        registered_by=ActorId(actor_id),
        decommissioned_at=None,
        decommissioned_by=None,
    )


@pytest.mark.unit
@given(
    display_name=_DISPLAY_NAME,
    now=aware_datetimes(),
    facility_id=st.uuids(),
    actor_id=st.uuids(),
)
def test_register_facility_site_emits_single_event_with_injected_fields(
    display_name: str,
    now: datetime,
    facility_id: UUID,
    actor_id: UUID,
) -> None:
    """Empty stream + valid SITE command (parent_id=None) -> single FacilityRegistered."""
    events = register_facility.decide(
        state=None,
        command=_command(kind=FacilityKind.SITE, parent_id=None, display_name=display_name),
        now=now,
        facility_id=FacilityId(facility_id),
        code=_CODE,
        registered_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == facility_id
    assert event.code == _CODE
    assert event.display_name == display_name
    assert event.kind is FacilityKind.SITE
    assert event.parent_id is None
    assert event.registered_by == actor_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    display_name=_DISPLAY_NAME,
    now=aware_datetimes(),
    facility_id=st.uuids(),
    parent_facility_id=st.uuids(),
    actor_id=st.uuids(),
)
def test_register_facility_area_emits_single_event_with_parent(
    display_name: str,
    now: datetime,
    facility_id: UUID,
    parent_facility_id: UUID,
    actor_id: UUID,
) -> None:
    """Empty stream + valid AREA command (parent_id non-None) + Site
    parent_lookup_result -> single FacilityRegistered."""
    parent_lookup = FacilityLookupResult(
        id=FacilityId(parent_facility_id),
        code=_CODE,
        kind=FacilityKind.SITE.value,
        status=FacilityStatus.ACTIVE.value,
        trust_anchor_credential_ids=frozenset(),
    )
    events = register_facility.decide(
        state=None,
        command=_command(
            kind=FacilityKind.AREA,
            parent_id=FacilityId(parent_facility_id),
            display_name=display_name,
            code="aps-area",
        ),
        now=now,
        facility_id=FacilityId(facility_id),
        code=_AREA_CODE,
        registered_by=ActorId(actor_id),
        parent_lookup_result=parent_lookup,
    )
    assert len(events) == 1
    event = events[0]
    assert event.kind is FacilityKind.AREA
    assert event.parent_id == parent_facility_id


@pytest.mark.unit
@given(
    existing_facility_id=st.uuids(),
    new_facility_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
    kind=st.sampled_from(list(FacilityKind)),
)
def test_register_facility_on_existing_state_always_raises_already_exists(
    existing_facility_id: UUID,
    new_facility_id: UUID,
    now: datetime,
    actor_id: UUID,
    kind: FacilityKind,
) -> None:
    """Any non-None state -> FacilityAlreadyExistsError, regardless of command."""
    parent_id: FacilityId | None = (
        None if kind is FacilityKind.SITE else FacilityId(new_facility_id)
    )
    command = _command(kind=kind, parent_id=parent_id)
    with pytest.raises(FacilityAlreadyExistsError) as exc:
        register_facility.decide(
            state=_existing_site_state(existing_facility_id, actor_id),
            command=command,
            now=now,
            facility_id=FacilityId(new_facility_id),
            code=_CODE,
            registered_by=ActorId(actor_id),
        )
    assert exc.value.code == _CODE


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    parent_facility_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_register_facility_site_with_non_null_parent_always_raises(
    facility_id: UUID,
    parent_facility_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """kind=Site + non-None parent_id -> FacilitySiteCannotHaveParentError, always."""
    command = _command(kind=FacilityKind.SITE, parent_id=FacilityId(parent_facility_id))
    with pytest.raises(FacilitySiteCannotHaveParentError) as exc:
        register_facility.decide(
            state=None,
            command=command,
            now=now,
            facility_id=FacilityId(facility_id),
            code=_CODE,
            registered_by=ActorId(actor_id),
        )
    assert exc.value.code == _CODE
    assert exc.value.parent_id == parent_facility_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_register_facility_area_with_null_parent_always_raises(
    facility_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """kind=Area + None parent_id -> FacilityAreaMustHaveParentError, always."""
    command = _command(kind=FacilityKind.AREA, parent_id=None, code="aps-area")
    with pytest.raises(FacilityAreaMustHaveParentError) as exc:
        register_facility.decide(
            state=None,
            command=command,
            now=now,
            facility_id=FacilityId(facility_id),
            code=_AREA_CODE,
            registered_by=ActorId(actor_id),
        )
    assert exc.value.code == _AREA_CODE


@pytest.mark.unit
@given(
    display_name=_DISPLAY_NAME,
    now=aware_datetimes(),
    facility_id=st.uuids(),
    actor_id=st.uuids(),
)
def test_register_facility_is_pure_same_input_same_output(
    display_name: str,
    now: datetime,
    facility_id: UUID,
    actor_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = _command(kind=FacilityKind.SITE, parent_id=None, display_name=display_name)
    first = register_facility.decide(
        state=None,
        command=command,
        now=now,
        facility_id=FacilityId(facility_id),
        code=_CODE,
        registered_by=ActorId(actor_id),
    )
    second = register_facility.decide(
        state=None,
        command=command,
        now=now,
        facility_id=FacilityId(facility_id),
        code=_CODE,
        registered_by=ActorId(actor_id),
    )
    assert first == second
