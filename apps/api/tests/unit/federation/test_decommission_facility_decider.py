"""Unit tests for the `decommission_facility` slice's pure decider.

Pin the not-found guard, the strict-not-idempotent already-decommissioned
guard, the Active -> Decommissioned transition, reason carriage,
purity, and handler-injected decommissioned_by / now capture.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityCannotDecommissionError,
    FacilityKind,
    FacilityName,
    FacilityNotFoundError,
    FacilityStatus,
)
from cora.federation.features import decommission_facility
from cora.federation.features.decommission_facility import DecommissionFacility
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-000000fed102"))
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed101"))
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed199"))
_CODE = FacilityCode("aps")


def _command(**overrides: object) -> DecommissionFacility:
    base: dict[str, object] = {
        "facility_id": _FACILITY_ID,
        "reason": "end-of-life",
    }
    base.update(overrides)
    return DecommissionFacility(**base)  # type: ignore[arg-type]


def _active_facility() -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=None,
        decommissioned_by=None,
    )


def _decommissioned_facility() -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.DECOMMISSIONED,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )


# ---------- not-found guard ----------


@pytest.mark.unit
def test_decommission_facility_rejects_none_state_as_not_found() -> None:
    with pytest.raises(FacilityNotFoundError) as exc:
        decommission_facility.decide(
            state=None,
            command=_command(),
            now=_NOW,
            decommissioned_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID


# ---------- already-decommissioned guard ----------


@pytest.mark.unit
def test_decommission_facility_rejects_already_decommissioned() -> None:
    with pytest.raises(FacilityCannotDecommissionError) as exc:
        decommission_facility.decide(
            state=_decommissioned_facility(),
            command=_command(),
            now=_NOW,
            decommissioned_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID


# ---------- valid transition ----------


@pytest.mark.unit
def test_decommission_facility_emits_one_event_for_active_state() -> None:
    events = decommission_facility.decide(
        state=_active_facility(),
        command=_command(),
        now=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == _FACILITY_ID
    assert event.decommissioned_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW
    assert event.reason == "end-of-life"


@pytest.mark.unit
def test_decommission_facility_accepts_none_reason() -> None:
    events = decommission_facility.decide(
        state=_active_facility(),
        command=_command(reason=None),
        now=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )
    assert events[0].reason is None


# ---------- purity + handler-injected capture ----------


@pytest.mark.unit
def test_decommission_facility_is_pure_same_inputs_same_outputs() -> None:
    state = _active_facility()
    first = decommission_facility.decide(
        state=state,
        command=_command(),
        now=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )
    second = decommission_facility.decide(
        state=state,
        command=_command(),
        now=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_decommission_facility_uses_handler_injected_actor_verbatim() -> None:
    injected = ActorId(uuid4())
    events = decommission_facility.decide(
        state=_active_facility(),
        command=_command(),
        now=_NOW,
        decommissioned_by=injected,
    )
    assert events[0].decommissioned_by == injected


@pytest.mark.unit
def test_decommission_facility_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2030, 12, 31, 23, 59, 59, tzinfo=UTC)
    events = decommission_facility.decide(
        state=_active_facility(),
        command=_command(),
        now=custom_now,
        decommissioned_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now
