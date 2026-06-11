"""Unit tests for CapabilitySummaryProjection.

Pins per-event-type apply() dispatch + the declarative-field refresh
shape for the 3 subscribed Capability events. Postgres-side behavior
(SQL execution + replay against a real bookmark) lives in the
integration tier; the cross-aggregate guard test below is the
projection-level counterpart of the earlier fix that exposed
FamilySummaryProjection silently dropping legacy events on replay.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.projections import CapabilitySummaryProjection

_CAPABILITY_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Capability",
        stream_id=_CAPABILITY_ID,
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
    proj = CapabilitySummaryProjection()
    assert proj.name == "proj_recipe_capability_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "CapabilityDefined",
            "CapabilityVersioned",
            "CapabilityDeprecated",
            "CapabilitySuggestedRolesUpdated",
        }
    )


@pytest.mark.unit
async def test_capability_defined_inserts_with_defined_status_and_null_version() -> None:
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(_CAPABILITY_ID),
            "code": "cora.capability.tomography",
            "name": "Tomography",
            "description": "Continuous-rotation tomographic acquisition.",
            "required_affordances": ["Rotatable", "Imageable"],
            "executor_shapes": ["Method"],
            "parameters_schema": {"$schema": "x", "type": "object"},
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_recipe_capability_summary" in sql
    assert "ON CONFLICT (capability_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == "cora.capability.tomography"
    assert args.args[3] == "Tomography"
    assert args.args[4] == "Continuous-rotation tomographic acquisition."
    assert args.args[5] == ["Rotatable", "Imageable"]
    assert args.args[6] == ["Method"]
    assert args.args[7] is True  # parameters_schema_present
    assert args.args[8] == _NOW


@pytest.mark.unit
async def test_capability_defined_tolerates_optional_fields_omitted() -> None:
    """Description and parameters_schema are both optional at define time;
    payload may omit them entirely (legacy / minimal Capabilities)."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(_CAPABILITY_ID),
            "code": "cora.capability.minimal",
            "name": "Minimal",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None  # description
    assert args.args[5] == []  # required_affordances default
    assert args.args[6] == []  # executor_shapes default
    assert args.args[7] is False  # parameters_schema_present


@pytest.mark.unit
async def test_capability_versioned_updates_status_and_refreshes_declarative_fields() -> None:
    """Per the projection docstring: a new version IS a new declaration, so
    description, required_affordances, executor_shapes, and the
    parameters_schema_present flag are ALL refreshed from the Versioned
    payload (the read model tracks the latest declaration, not the
    define-time one)."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityVersioned",
        {
            "capability_id": str(_CAPABILITY_ID),
            "version_tag": "v2.1.0",
            "description": "Now with bonus features.",
            "required_affordances": ["Rotatable", "Imageable", "Triggerable"],
            "executor_shapes": ["Method", "Procedure"],
            "parameters_schema": {"$schema": "x", "type": "object"},
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_capability_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert "version_tag = $2" in sql
    assert "description = $3" in sql
    assert "required_affordances = $4" in sql
    assert "executor_shapes = $5" in sql
    assert "parameters_schema_present = $6" in sql
    assert "versioned_at = $7" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == "v2.1.0"
    assert args.args[3] == "Now with bonus features."
    assert args.args[4] == ["Rotatable", "Imageable", "Triggerable"]
    assert args.args[5] == ["Method", "Procedure"]
    assert args.args[6] is True
    assert args.args[7] == _NOW


@pytest.mark.unit
async def test_capability_versioned_with_no_parameters_schema_sets_present_false() -> None:
    """Clearing the schema across a version bump flips the flag back to
    FALSE: the read model reflects the latest declaration, including
    the absence of a schema."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityVersioned",
        {
            "capability_id": str(_CAPABILITY_ID),
            "version_tag": "v3.0.0",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[6] is False


@pytest.mark.unit
async def test_capability_deprecated_updates_status_and_replaced_by_id() -> None:
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    replaced_by = uuid4()
    event = _stored(
        "CapabilityDeprecated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "replaced_by_capability_id": str(replaced_by),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_capability_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "replaced_by_capability_id = $2" in sql
    assert "deprecated_at = $3" in sql
    # Declarative fields are preserved for audit per the projection docstring.
    assert "description" not in sql
    assert "required_affordances" not in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == replaced_by
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_capability_deprecated_without_replaced_by_sets_null() -> None:
    """`replaced_by_capability_id` is optional on the Deprecated event
    (terminal-without-successor case). Projection must coerce the
    missing key to NULL rather than crash on `UUID(None)`."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityDeprecated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] is None


# ---------- gate-review fill-ins (Path C) ----------


@pytest.mark.unit
async def test_capability_versioned_replayed_overwrites_versioned_at() -> None:
    """Path C: re-version replaces versioned_at wholesale (state-always-
    holds-latest convention mirrored in projection). Mirrors the equivalent
    test on Method."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    later = datetime(2026, 6, 1, 9, 30, 0, tzinfo=UTC)

    first = _stored(
        "CapabilityVersioned",
        {
            "capability_id": str(_CAPABILITY_ID),
            "version_tag": "v1.0.0",
            "occurred_at": _NOW.isoformat(),
        },
    )
    second = _stored(
        "CapabilityVersioned",
        {
            "capability_id": str(_CAPABILITY_ID),
            "version_tag": "v2.0.0",
            "occurred_at": later.isoformat(),
        },
    )

    await proj.apply(first, conn)
    await proj.apply(second, conn)

    assert conn.execute.await_count == 2
    second_args = conn.execute.await_args_list[1].args
    # versioned_at sits at $7 (after version_tag, description,
    # required_affordances, executor_shapes, parameters_schema_present).
    assert second_args[2] == "v2.0.0"
    assert second_args[7] == later


@pytest.mark.unit
async def test_capability_lifecycle_timestamps_is_immutable_dataclass() -> None:
    """CapabilityLifecycleTimestamps is the projection-sourced VO read by
    the route layer (Path C). Frozen so callers can't mutate it under cached
    references; field shape pinned so future widening shows up as a deliberate
    change. Distinct from `replaced_by_capability_id` (intrinsic state field,
    catalog governance)."""
    import dataclasses

    from cora.recipe.aggregates.capability import CapabilityLifecycleTimestamps

    assert dataclasses.is_dataclass(CapabilityLifecycleTimestamps)
    field_names = {f.name for f in dataclasses.fields(CapabilityLifecycleTimestamps)}
    assert field_names == {"created_at", "versioned_at", "deprecated_at"}

    instance = CapabilityLifecycleTimestamps(
        created_at=_NOW,
        versioned_at=None,
        deprecated_at=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.versioned_at = _NOW  # type: ignore[misc]


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    """The bare `case _: pass` arm is the safety net if the SQL-side
    event_type filter ever lets a non-subscribed event through:
    apply() must NOT execute against the read model."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_method_defined_is_silently_dropped() -> None:
    """Cross-aggregate-event guard mirroring the 5i P0 fix shape: a
    Method-aggregate event arriving at the Capability projection must
    drop silently. Cheap insurance against an event-type rename or a
    subscribed-set drift."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored("MethodDefined", {"method_id": str(uuid4())})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_capability_defined_seeds_empty_suggested_roles() -> None:
    """Layer 3 sub-slice 3E: INSERT defaults suggested_roles to
    ARRAY[]::UUID[]."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(_CAPABILITY_ID),
            "code": "cora.capability.acquire",
            "name": "Acquire",
            "description": None,
            "required_affordances": [],
            "executor_shapes": ["Method"],
            "parameters_schema": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "ARRAY[]::UUID[]" in sql  # suggested_role_ids defaults empty
    assert "suggested_role_ids" in sql


@pytest.mark.unit
async def test_capability_suggested_roles_updated_writes_wholesale_replacement() -> None:
    """Wholesale-replace shape: UPDATE writes the FULL new set."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    rid_a = uuid4()
    rid_b = uuid4()
    event = _stored(
        "CapabilitySuggestedRolesUpdated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "suggested_role_ids": [str(rid_a), str(rid_b)],
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "SET suggested_role_ids = $2" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert set(args.args[2]) == {rid_a, rid_b}


@pytest.mark.unit
async def test_capability_suggested_roles_updated_clears_with_empty_set() -> None:
    """Empty payload clears the column wholesale."""
    proj = CapabilitySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CapabilitySuggestedRolesUpdated",
        {
            "capability_id": str(_CAPABILITY_ID),
            "suggested_role_ids": [],
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == []
