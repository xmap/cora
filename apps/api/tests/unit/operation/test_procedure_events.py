"""Procedure event (de)serialization + roundtrip tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation.aggregates.procedure import (
    STEPS_LOGBOOK_SCHEMA,
    ProcedureAborted,
    ProcedureCompleted,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStepsLogbookOpened,
    ProcedureTruncated,
    RecipeExpansionRecorded,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Procedure",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_for_procedure_registered() -> None:
    event = ProcedureRegistered(
        procedure_id=uuid4(),
        name="X",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureRegistered"


@pytest.mark.unit
def test_to_payload_serializes_procedure_registered_to_primitives() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000a001")
    asset1 = UUID("01900000-0000-7000-8000-00000000a002")
    asset2 = UUID("01900000-0000-7000-8000-00000000a003")
    parent_run = UUID("01900000-0000-7000-8000-00000000a004")
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset2, asset1),  # unsorted input
        parent_run_id=parent_run,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "name": "2-BM rotation-axis alignment",
        "kind": "alignment",
        # Sorted by string form for deterministic payload bytes.
        "target_asset_ids": sorted([str(asset1), str(asset2)]),
        "parent_run_id": str(parent_run),
        # capability_id (default). Pre-binding streams omit the key
        # and fold via `.get("capability_id")` in from_stored.
        "capability_id": None,
        # recipe_id (default). Pre-Recipe-rewrite streams omit the
        # key and fold via `.get("recipe_id")` in from_stored.
        # `register_procedure_from_recipe` sets both `recipe_id` and
        # the denorm `capability_id`; the legacy `register_procedure`
        # slice leaves both None.
        "recipe_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_standalone_procedure_with_null_parent() -> None:
    """Standalone procedures (bakeouts, etc.) have parent_run_id=None."""
    event = ProcedureRegistered(
        procedure_id=uuid4(),
        name="Vessel-A bakeout",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["parent_run_id"] is None
    assert payload["target_asset_ids"] == []


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_registered() -> None:
    procedure_id = uuid4()
    asset1 = uuid4()
    parent_run = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(procedure_id),
            "name": "X",
            "kind": "bakeout",
            "target_asset_ids": [str(asset1)],
            "parent_run_id": str(parent_run),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.name == "X"
    assert rebuilt.kind == "bakeout"
    assert rebuilt.target_asset_ids == (asset1,)
    assert rebuilt.parent_run_id == parent_run


@pytest.mark.unit
def test_from_stored_rebuilds_standalone_procedure_with_null_parent() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(procedure_id),
            "name": "Vessel-A bakeout",
            "kind": "bakeout",
            "target_asset_ids": [],
            "parent_run_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.parent_run_id is None
    assert rebuilt.target_asset_ids == ()


@pytest.mark.unit
def test_from_stored_rebuilds_pre_10d_procedure_registered_without_capability_id_key() -> None:
    """Additive backwards-compat pin: legacy streams omit
    the `capability_id` key from `ProcedureRegistered` payloads
    entirely. `from_stored` MUST use `payload.get("capability_id")`
    sentinel-default-None so legacy streams fold cleanly without
    backfill. Mirrors the additive-evolution shape locked for
    Method.capability_id and Method.needed_supplies."""
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            # NOTE: NO "capability_id" key — legacy shape.
            "procedure_id": str(procedure_id),
            "name": "Vessel-A bakeout",
            "kind": "bakeout",
            "target_asset_ids": [],
            "parent_run_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.capability_id is None


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_registered_with_capability_id() -> None:
    """Additive evolution: current streams carry `capability_id` as a
    UUID string in the payload; `from_stored` converts it back to a
    UUID instance in the rebuilt event."""
    procedure_id = uuid4()
    capability_id = uuid4()
    stored = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(procedure_id),
            "name": "Hexapod reboot",
            "kind": "recovery",
            "target_asset_ids": [],
            "parent_run_id": None,
            "capability_id": str(capability_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    assert rebuilt.capability_id == capability_id


@pytest.mark.unit
def test_procedure_registered_round_trips() -> None:
    asset1 = uuid4()
    asset2 = uuid4()
    parent_run = uuid4()
    original = ProcedureRegistered(
        procedure_id=uuid4(),
        name="2-BM rotation-axis alignment",
        kind="alignment",
        target_asset_ids=(asset1, asset2),
        parent_run_id=parent_run,
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureRegistered", to_payload(original))
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureRegistered)
    # Sets equal: payload sorts; from_stored preserves payload order.
    assert set(rebuilt.target_asset_ids) == set(original.target_asset_ids)
    assert rebuilt.procedure_id == original.procedure_id
    assert rebuilt.parent_run_id == original.parent_run_id


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("BogusEvent", {})
    with pytest.raises(ValueError, match="Unknown ProcedureEvent event_type"):
        from_stored(stored)


# --- 10c-b transition events ---


@pytest.mark.unit
def test_event_type_name_for_procedure_started() -> None:
    event = ProcedureStarted(procedure_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "ProcedureStarted"


@pytest.mark.unit
def test_event_type_name_for_procedure_completed() -> None:
    event = ProcedureCompleted(procedure_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "ProcedureCompleted"


@pytest.mark.unit
def test_event_type_name_for_procedure_aborted() -> None:
    event = ProcedureAborted(procedure_id=uuid4(), reason="x", occurred_at=_NOW)
    assert event_type_name(event) == "ProcedureAborted"


@pytest.mark.unit
def test_to_payload_serializes_procedure_started() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b001")
    event = ProcedureStarted(procedure_id=procedure_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_completed() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b002")
    event = ProcedureCompleted(procedure_id=procedure_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_aborted() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000b003")
    event = ProcedureAborted(procedure_id=procedure_id, reason="quench", occurred_at=_NOW)
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "reason": "quench",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_started() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureStarted",
        {"procedure_id": str(procedure_id), "occurred_at": _NOW.isoformat()},
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureStarted)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.occurred_at == _NOW


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_completed() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureCompleted",
        {"procedure_id": str(procedure_id), "occurred_at": _NOW.isoformat()},
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureCompleted)
    assert rebuilt.procedure_id == procedure_id


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_aborted() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureAborted",
        {
            "procedure_id": str(procedure_id),
            "reason": "vacuum loss",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureAborted)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.reason == "vacuum loss"


@pytest.mark.unit
def test_procedure_started_round_trips() -> None:
    original = ProcedureStarted(procedure_id=uuid4(), occurred_at=_NOW)
    stored = _stored("ProcedureStarted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_procedure_completed_round_trips() -> None:
    original = ProcedureCompleted(procedure_id=uuid4(), occurred_at=_NOW)
    stored = _stored("ProcedureCompleted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_procedure_aborted_round_trips() -> None:
    original = ProcedureAborted(procedure_id=uuid4(), reason="hardware fault", occurred_at=_NOW)
    stored = _stored("ProcedureAborted", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


# --- ProcedureStepsLogbookOpened (lazy-open envelope) ---


@pytest.mark.unit
def test_event_type_name_for_procedure_steps_logbook_opened() -> None:
    event = ProcedureStepsLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="steps",
        schema=STEPS_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureStepsLogbookOpened"


@pytest.mark.unit
def test_to_payload_serializes_procedure_steps_logbook_opened() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000c001")
    logbook_id = UUID("01900000-0000-7000-8000-00000000c002")
    schema = LogbookSchema(
        fields={"step_kind": LogbookFieldSpec(type="string")},
        description="test",
    )
    event = ProcedureStepsLogbookOpened(
        procedure_id=procedure_id,
        logbook_id=logbook_id,
        kind="steps",
        schema=schema,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["procedure_id"] == str(procedure_id)
    assert payload["logbook_id"] == str(logbook_id)
    assert payload["kind"] == "steps"
    assert payload["schema"] == schema.to_dict()
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_steps_logbook_opened() -> None:
    procedure_id = uuid4()
    logbook_id = uuid4()
    schema = STEPS_LOGBOOK_SCHEMA
    stored = _stored(
        "ProcedureStepsLogbookOpened",
        {
            "procedure_id": str(procedure_id),
            "logbook_id": str(logbook_id),
            "kind": "steps",
            "schema": schema.to_dict(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureStepsLogbookOpened)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.logbook_id == logbook_id
    assert rebuilt.kind == "steps"
    assert rebuilt.schema == schema


@pytest.mark.unit
def test_procedure_steps_logbook_opened_round_trips() -> None:
    original = ProcedureStepsLogbookOpened(
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        kind="steps",
        schema=STEPS_LOGBOOK_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureStepsLogbookOpened", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


# --- ProcedureTruncated (partial-data terminal) ---


@pytest.mark.unit
def test_event_type_name_for_procedure_truncated() -> None:
    event = ProcedureTruncated(
        procedure_id=uuid4(),
        reason="weekend power loss",
        interrupted_at=_NOW,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "ProcedureTruncated"


@pytest.mark.unit
def test_to_payload_serializes_procedure_truncated_with_interrupted_at() -> None:
    procedure_id = UUID("01900000-0000-7000-8000-00000000d001")
    interrupted_at = _NOW - timedelta(hours=2)
    event = ProcedureTruncated(
        procedure_id=procedure_id,
        reason="vacuum loss",
        interrupted_at=interrupted_at,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "procedure_id": str(procedure_id),
        "reason": "vacuum loss",
        "interrupted_at": interrupted_at.isoformat(),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_procedure_truncated_with_null_interrupted_at() -> None:
    """interrupted_at is optional; None serializes as null."""
    event = ProcedureTruncated(
        procedure_id=uuid4(),
        reason="unknown when crashed",
        interrupted_at=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["interrupted_at"] is None


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_truncated_with_interrupted_at() -> None:
    procedure_id = uuid4()
    interrupted_at = _NOW - timedelta(hours=3)
    stored = _stored(
        "ProcedureTruncated",
        {
            "procedure_id": str(procedure_id),
            "reason": "hardware fault",
            "interrupted_at": interrupted_at.isoformat(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureTruncated)
    assert rebuilt.procedure_id == procedure_id
    assert rebuilt.reason == "hardware fault"
    assert rebuilt.interrupted_at == interrupted_at


@pytest.mark.unit
def test_from_stored_rebuilds_procedure_truncated_with_null_interrupted_at() -> None:
    procedure_id = uuid4()
    stored = _stored(
        "ProcedureTruncated",
        {
            "procedure_id": str(procedure_id),
            "reason": "unknown",
            "interrupted_at": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, ProcedureTruncated)
    assert rebuilt.interrupted_at is None


@pytest.mark.unit
def test_procedure_truncated_round_trips() -> None:
    original = ProcedureTruncated(
        procedure_id=uuid4(),
        reason="weekend power loss",
        interrupted_at=_NOW - timedelta(hours=12),
        occurred_at=_NOW,
    )
    stored = _stored("ProcedureTruncated", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_to_payload_bindings_field_is_dict_after_canonical_json_hoist() -> None:
    """The events.py `to_payload(RecipeExpansionRecorded)` arm uses
    `json.loads(canonical_json_bytes(dict(bindings)))` so the persisted
    payload `bindings` field stays a dict (the shape `from_stored`'s
    `dict(payload['bindings'])` consumer expects). A future refactor
    that drops the `json.loads(...)` wrapper (e.g., `.decode('utf-8')`)
    would persist a JSON string and break round-trip; this test pins
    the dict shape.
    """
    event = RecipeExpansionRecorded(
        procedure_id=uuid4(),
        recipe_id=uuid4(),
        recipe_version="v1",
        capability_id=uuid4(),
        capability_version=None,
        bindings={"beta": 2.0, "alpha": 1.0},
        expansion_port_version="v1",
        steps_hash="aaaa",
        bindings_hash="bbbb",
        step_count=1,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert isinstance(payload["bindings"], dict)
    assert payload["bindings"] == {"alpha": 1.0, "beta": 2.0}
    rebuilt = from_stored(_stored("RecipeExpansionRecorded", payload))
    assert rebuilt.bindings == event.bindings  # type: ignore[union-attr]


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureCompleted",
        "ProcedureAborted",
        "ProcedureTruncated",
        "ProcedureStepsLogbookOpened",
    ],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """Per the convention adopted post-corpus-survey (Marten /
    pyeventsourcing / Pydantic / msgspec all wrap), each event-type case
    wraps `KeyError`/`TypeError`/`AttributeError` into a tagged
    `ValueError` so a corrupted event row fails loud with the event-type
    name in the message rather than bubbling a raw KeyError from deep
    in the load path."""
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(_stored(event_type, {}))
