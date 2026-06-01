"""Unit tests for ModelSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 5
subscribed Model events. Postgres-side behavior (vendor-key UNIQUE
index, JSONB re-aggregation correctness, replay safety) is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections import ModelSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_MODEL_ID = uuid4()
_FAMILY_A_ID = uuid4()
_FAMILY_B_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 1, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Model",
        stream_id=_MODEL_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = ModelSummaryProjection()
    assert proj.name == "proj_equipment_model_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "ModelDefined",
            "ModelVersioned",
            "ModelDeprecated",
            "ModelFamilyAdded",
            "ModelFamilyRemoved",
        }
    )


@pytest.mark.unit
async def test_projection_does_not_subscribe_to_family_or_asset_events() -> None:
    """Cross-aggregate guard: Family and Asset events belong in their
    own projection modules."""
    proj = ModelSummaryProjection()
    assert "FamilyDefined" not in proj.subscribed_event_types
    assert "AssetRegistered" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_model_defined_inserts_row_with_defined_status() -> None:
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ModelDefined",
        {
            "model_id": str(_MODEL_ID),
            "name": "Aerotech ANT130-L",
            "manufacturer": {"name": "Aerotech"},
            "part_number": "ANT130-L",
            "declared_families": [str(_FAMILY_A_ID)],
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_equipment_model_summary" in sql
    assert "ON CONFLICT (model_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert args.args[1] == _MODEL_ID
    assert args.args[2] == "Aerotech ANT130-L"
    assert args.args[3] == "Aerotech"
    # manufacturer_identifier + identifier_type both None (optional pair).
    assert args.args[4] is None
    assert args.args[5] is None
    assert args.args[6] == "ANT130-L"
    # declared_families serialized as a JSON-string payload.
    assert args.args[7] == f'["{_FAMILY_A_ID}"]'
    # version_tag absent in payload -> None bound.
    assert args.args[8] is None
    assert args.args[9] == _NOW


@pytest.mark.unit
async def test_model_defined_with_optional_manufacturer_identifier_pair() -> None:
    """The optional manufacturer-identifier pair lands on the flat
    `manufacturer_identifier` + `manufacturer_identifier_type` columns
    (both set or both null per the VO's pairing invariant)."""
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ModelDefined",
        {
            "model_id": str(_MODEL_ID),
            "name": "Aerotech ANT130-L",
            "manufacturer": {
                "name": "Aerotech",
                "identifier": "https://ror.org/02jbv0t02",
                "identifier_type": "ROR",
            },
            "part_number": "ANT130-L",
            "declared_families": [str(_FAMILY_A_ID)],
            "occurred_at": _NOW.isoformat(),
            "version_tag": "rev-A",
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[3] == "Aerotech"
    assert args.args[4] == "https://ror.org/02jbv0t02"
    assert args.args[5] == "ROR"
    # version_tag carried on Defined when present.
    assert args.args[8] == "rev-A"


@pytest.mark.unit
async def test_model_versioned_updates_status_and_replaces_identity_block() -> None:
    """ModelVersioned writes status=Versioned AND replaces the full
    identity block (name, manufacturer, part_number, declared_families,
    version_tag) wholesale."""
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ModelVersioned",
        {
            "model_id": str(_MODEL_ID),
            "name": "Aerotech ANT130-LZS",
            "manufacturer": {"name": "Aerotech"},
            "part_number": "ANT130-LZS",
            "declared_families": [str(_FAMILY_A_ID), str(_FAMILY_B_ID)],
            "version_tag": "v2.1.0",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_model_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert "name = $2" in sql
    assert "manufacturer_name = $3" in sql
    assert "part_number = $6" in sql
    assert "declared_families = $7" in sql
    assert "version_tag = $8" in sql
    assert args.args[1] == _MODEL_ID
    assert args.args[2] == "Aerotech ANT130-LZS"
    assert args.args[3] == "Aerotech"
    assert args.args[6] == "ANT130-LZS"
    assert args.args[8] == "v2.1.0"


@pytest.mark.unit
async def test_model_deprecated_updates_status_and_sets_reason() -> None:
    """ModelDeprecated sets status=Deprecated + deprecation_reason and
    intentionally leaves vendor-key columns alone so the audit trail
    of "what was deprecated" stays answerable."""
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ModelDeprecated",
        {
            "model_id": str(_MODEL_ID),
            "reason": "Superseded by ANT130-LZS",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_model_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "deprecation_reason = $2" in sql
    # Vendor-key + identity columns NOT touched on Deprecated.
    assert "manufacturer_name" not in sql
    assert "part_number" not in sql
    assert "declared_families" not in sql
    assert "version_tag" not in sql
    assert args.args[1] == _MODEL_ID
    assert args.args[2] == "Superseded by ANT130-LZS"


@pytest.mark.unit
async def test_model_family_added_appends_to_jsonb_declared_families() -> None:
    """ModelFamilyAdded re-aggregates the JSONB declared_families
    column via pure SQL (UNION + jsonb_agg ORDER BY) to append a
    single family_id and preserve canonical sort order."""
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ModelFamilyAdded",
        {
            "model_id": str(_MODEL_ID),
            "family_id": str(_FAMILY_B_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_model_summary" in sql
    assert "declared_families" in sql
    assert "jsonb_array_elements_text" in sql
    assert "UNION" in sql
    assert "jsonb_agg" in sql
    assert args.args[1] == _MODEL_ID
    assert args.args[2] == str(_FAMILY_B_ID)


@pytest.mark.unit
async def test_model_family_removed_drops_family_from_jsonb() -> None:
    """ModelFamilyRemoved re-aggregates the JSONB declared_families
    column to drop a single family_id while preserving sort order."""
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ModelFamilyRemoved",
        {
            "model_id": str(_MODEL_ID),
            "family_id": str(_FAMILY_B_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_model_summary" in sql
    assert "declared_families" in sql
    assert "jsonb_array_elements_text" in sql
    # Filter clause drops the removed id, no UNION.
    assert "WHERE elem <> $2::text" in sql
    assert args.args[1] == _MODEL_ID
    assert args.args[2] == str(_FAMILY_B_ID)


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_family_defined_is_silently_dropped() -> None:
    """Cross-aggregate-event guard: FamilyDefined is not in
    subscribed_event_types, but if the SQL filter ever lets one
    through, the bare match drops it without error."""
    proj = ModelSummaryProjection()
    conn = AsyncMock()
    event = _stored("FamilyDefined", {"family_id": str(uuid4())})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
