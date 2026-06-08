"""Unit tests for the Federation BC's self-Facility bootstrap seed."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation import bootstrap_federation
from cora.federation.aggregates.facility import (
    FacilityKind,
    FacilityStatus,
    facility_stream_id,
    load_facility,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.facility_code import (
    FacilityCode,
    InvalidFacilityCodeError,
)

_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)


def _kernel(*, self_facility_code: str = "aps") -> Kernel:
    settings = Settings(self_facility_code=self_facility_code)  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        # Two ids per seed call: event_id + correlation_id.
        id_generator=FixedIdGenerator(
            [
                UUID("01900000-0000-7000-8000-00000000ee01"),
                UUID("01900000-0000-7000-8000-00000000c001"),
                UUID("01900000-0000-7000-8000-00000000ee02"),
                UUID("01900000-0000-7000-8000-00000000c002"),
            ]
        ),
        authz=AllowAllAuthorize(),
    )


# ---------- first call: writes the self-Facility row ----------


@pytest.mark.unit
async def test_bootstrap_seeds_self_facility_row() -> None:
    kernel = _kernel(self_facility_code="aps")
    await bootstrap_federation(kernel)

    expected_id = facility_stream_id(FacilityCode("aps"))
    facility = await load_facility(kernel.event_store, expected_id)
    assert facility is not None
    assert facility.id == expected_id
    assert facility.code == FacilityCode("aps")
    assert facility.display_name.value == "aps"
    assert facility.kind is FacilityKind.SITE
    assert facility.parent_id is None
    assert facility.status is FacilityStatus.ACTIVE
    assert facility.trust_anchor_credential_ids == frozenset()
    assert facility.alternate_identifiers == frozenset()
    assert facility.persistent_id is None
    assert facility.registered_at == _NOW
    assert facility.registered_by == SYSTEM_PRINCIPAL_ID
    assert facility.decommissioned_at is None
    assert facility.decommissioned_by is None


@pytest.mark.unit
async def test_bootstrap_uses_settings_self_facility_code() -> None:
    """Different env values produce distinct stream ids and distinct
    Facility.code values."""
    kernel = _kernel(self_facility_code="maxiv")
    await bootstrap_federation(kernel)

    expected_id = facility_stream_id(FacilityCode("maxiv"))
    facility = await load_facility(kernel.event_store, expected_id)
    assert facility is not None
    assert facility.code == FacilityCode("maxiv")


# ---------- idempotency: repeated seed calls do not duplicate ----------


@pytest.mark.unit
async def test_bootstrap_is_idempotent_across_calls() -> None:
    """A repeated seed call (on every app boot) MUST NOT raise and
    MUST NOT duplicate the Facility row."""
    kernel = _kernel(self_facility_code="aps")
    await bootstrap_federation(kernel)
    # Second call swallows ConcurrencyError as the "already seeded" signal.
    await bootstrap_federation(kernel)

    expected_id = facility_stream_id(FacilityCode("aps"))
    events, version = await kernel.event_store.load("Facility", expected_id)
    # Exactly one FacilityRegistered event; second call did not append.
    assert version == 1
    assert len(events) == 1


# ---------- fail-fast on misconfigured code ----------


@pytest.mark.unit
async def test_bootstrap_fails_fast_on_invalid_facility_code() -> None:
    """SELF_FACILITY_CODE with uppercase / spaces / invalid codepoints
    fails at FacilityCode(...) construction, surfacing as
    InvalidFacilityCodeError before any event-store write."""
    kernel = _kernel(self_facility_code="Has Uppercase")
    with pytest.raises(InvalidFacilityCodeError):
        await bootstrap_federation(kernel)


# ---------- principal_id stamp ----------


@pytest.mark.unit
async def test_bootstrap_stamps_system_principal_id() -> None:
    """The seed-emitted event carries principal_id=SYSTEM_PRINCIPAL_ID
    (not the bootstrap policy id; not an actor id)."""
    kernel = _kernel(self_facility_code="aps")
    await bootstrap_federation(kernel)
    expected_id = facility_stream_id(FacilityCode("aps"))
    events, _version = await kernel.event_store.load("Facility", expected_id)
    assert events[0].principal_id == SYSTEM_PRINCIPAL_ID


# ---------- no Decision audit cross-write ----------


@pytest.mark.unit
async def test_bootstrap_does_not_write_decision_stream() -> None:
    """The bootstrap is a system-driven structural write; no
    Decision audit per the register_facility / decommission_facility
    single-stream pattern."""
    kernel = _kernel(self_facility_code="aps")
    await bootstrap_federation(kernel)
    decision_events, decision_version = await kernel.event_store.load(
        "Decision", UUID("00000000-0000-0000-0000-000000000099")
    )
    assert decision_version == 0
    assert decision_events == []
