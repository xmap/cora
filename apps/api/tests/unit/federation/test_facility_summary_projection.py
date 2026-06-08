"""Unit tests for FacilitySummaryProjection."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from cora.federation.projections.facility import FacilitySummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))

_FACILITY_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)


def _conn_with_savepoint() -> AsyncMock:
    """AsyncMock conn whose `transaction()` returns an async context manager.

    The projection's `FacilityRegistered` arm wraps its INSERT in
    `async with conn.transaction(): ...` so the (code) UNIQUE constraint
    on `proj_federation_facility_summary` rolls back only the inner
    SAVEPOINT (not the worker's outer batch txn). The unit test mock
    needs to satisfy that protocol shape (mirrors
    `tests/unit/caution/test_caution_summary_projection.py::_conn_with_savepoint`).
    """
    conn = AsyncMock()
    transaction_cm = AsyncMock()
    transaction_cm.__aenter__.return_value = None
    transaction_cm.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=transaction_cm)
    return conn


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Facility",
        stream_id=_FACILITY_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    """Per feedback_projection_metadata_test: static frozenset assertion
    guards against silent subscription drift across CI parallelization."""
    proj = FacilitySummaryProjection()
    assert proj.name == "proj_federation_facility_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "FacilityRegistered",
            "FacilityDecommissioned",
            "FacilityTrustAnchorCredentialAdded",
            "FacilityTrustAnchorCredentialRemoved",
        }
    )


# ---------- FacilityRegistered apply ----------


@pytest.mark.unit
async def test_facility_registered_inserts_site_row() -> None:
    proj = FacilitySummaryProjection()
    conn = _conn_with_savepoint()
    event = _stored(
        "FacilityRegistered",
        {
            "facility_id": str(_FACILITY_ID),
            "code": "aps",
            "display_name": "Advanced Photon Source",
            "kind": "Site",
            "parent_id": None,
            "alternate_identifiers": [],
            "registered_by": str(_TEST_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    # Positional args: facility_id, code, display_name, kind, parent_id,
    # alternate_identifiers, registered_at, registered_by.
    assert args.args[1] == _FACILITY_ID
    assert args.args[2] == "aps"
    assert args.args[3] == "Advanced Photon Source"
    assert args.args[4] == "Site"
    assert args.args[5] is None
    assert args.args[6] == []
    assert args.args[7] == _NOW
    assert args.args[8] == _TEST_ACTOR_ID


@pytest.mark.unit
async def test_facility_registered_inserts_area_with_parent_id() -> None:
    proj = FacilitySummaryProjection()
    conn = _conn_with_savepoint()
    parent_id = uuid4()
    event = _stored(
        "FacilityRegistered",
        {
            "facility_id": str(_FACILITY_ID),
            "code": "2-bm",
            "display_name": "2-BM Beamline",
            "kind": "Area",
            "parent_id": str(parent_id),
            "alternate_identifiers": [],
            "registered_by": str(_TEST_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] == "Area"
    assert args.args[5] == parent_id


@pytest.mark.unit
async def test_facility_registered_preserves_alternate_identifiers_jsonb() -> None:
    proj = FacilitySummaryProjection()
    conn = _conn_with_savepoint()
    alts = [
        {"kind": "SerialNumber", "value": "APS-2BM"},
        {"kind": "Other", "value": "aps-id-42"},
    ]
    event = _stored(
        "FacilityRegistered",
        {
            "facility_id": str(_FACILITY_ID),
            "code": "aps",
            "display_name": "Advanced Photon Source",
            "kind": "Site",
            "parent_id": None,
            "alternate_identifiers": alts,
            "registered_by": str(_TEST_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[6] == alts


# ---------- FacilityDecommissioned apply ----------


@pytest.mark.unit
async def test_facility_decommissioned_updates_status_and_timestamps() -> None:
    proj = FacilitySummaryProjection()
    conn = AsyncMock()
    decommissioned_at = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
    event = _stored(
        "FacilityDecommissioned",
        {
            "facility_id": str(_FACILITY_ID),
            "decommissioned_by": str(_TEST_ACTOR_ID),
            "occurred_at": decommissioned_at.isoformat(),
            "reason": "end-of-life",
        },
    )
    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    # Positional args after SQL: facility_id, decommissioned_at, decommissioned_by.
    assert args.args[1] == _FACILITY_ID
    assert args.args[2] == decommissioned_at
    assert args.args[3] == _TEST_ACTOR_ID


# ---------- FacilityTrustAnchorCredentialAdded apply ----------


@pytest.mark.unit
async def test_facility_trust_anchor_credential_added_updates_jsonb_array() -> None:
    proj = FacilitySummaryProjection()
    conn = AsyncMock()
    credential_id = uuid4()
    event = _stored(
        "FacilityTrustAnchorCredentialAdded",
        {
            "facility_id": str(_FACILITY_ID),
            "credential_id": str(credential_id),
            "added_by": str(_TEST_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[1] == _FACILITY_ID
    assert args.args[2] == str(credential_id)


# ---------- FacilityTrustAnchorCredentialRemoved apply ----------


@pytest.mark.unit
async def test_facility_trust_anchor_credential_removed_updates_jsonb_array() -> None:
    proj = FacilitySummaryProjection()
    conn = AsyncMock()
    credential_id = uuid4()
    event = _stored(
        "FacilityTrustAnchorCredentialRemoved",
        {
            "facility_id": str(_FACILITY_ID),
            "credential_id": str(credential_id),
            "removed_by": str(_TEST_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
            "reason": "key compromise",
        },
    )
    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[1] == _FACILITY_ID
    assert args.args[2] == str(credential_id)
