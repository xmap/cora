"""CautionEvent serialization round-trips + serialize_target / deserialize_target."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionRegistered,
    CautionRetired,
    CautionSuperseded,
    ProcedureTarget,
    deserialize_target,
    event_type_name,
    from_stored,
    serialize_target,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAUTION_ID = UUID("01900000-0000-7000-8000-00000000b001")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000b002")
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-00000000b003")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000b004"))


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Caution",
        stream_id=_CAUTION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- serialize_target / deserialize_target ----------


@pytest.mark.unit
def test_serialize_target_for_asset() -> None:
    target = AssetTarget(asset_id=_ASSET_ID)
    assert serialize_target(target) == {"kind": "Asset", "id": str(_ASSET_ID)}


@pytest.mark.unit
def test_serialize_target_for_procedure() -> None:
    target = ProcedureTarget(procedure_id=_PROCEDURE_ID)
    assert serialize_target(target) == {"kind": "Procedure", "id": str(_PROCEDURE_ID)}


@pytest.mark.unit
def test_deserialize_target_for_asset() -> None:
    target = deserialize_target({"kind": "Asset", "id": str(_ASSET_ID)})
    assert target == AssetTarget(asset_id=_ASSET_ID)


@pytest.mark.unit
def test_deserialize_target_for_procedure() -> None:
    target = deserialize_target({"kind": "Procedure", "id": str(_PROCEDURE_ID)})
    assert target == ProcedureTarget(procedure_id=_PROCEDURE_ID)


@pytest.mark.unit
def test_target_round_trip_asset() -> None:
    original = AssetTarget(asset_id=_ASSET_ID)
    rebuilt = deserialize_target(serialize_target(original))
    assert rebuilt == original


@pytest.mark.unit
def test_target_round_trip_procedure() -> None:
    original = ProcedureTarget(procedure_id=_PROCEDURE_ID)
    rebuilt = deserialize_target(serialize_target(original))
    assert rebuilt == original


@pytest.mark.unit
def test_deserialize_target_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown CautionTarget kind"):
        deserialize_target({"kind": "Run", "id": str(uuid4())})


@pytest.mark.unit
def test_deserialize_target_rejects_missing_kind() -> None:
    with pytest.raises(ValueError, match="Malformed CautionTarget payload"):
        deserialize_target({"id": str(uuid4())})


@pytest.mark.unit
def test_deserialize_target_rejects_missing_id() -> None:
    with pytest.raises(ValueError, match="Malformed CautionTarget payload"):
        deserialize_target({"kind": "Asset"})


@pytest.mark.unit
def test_deserialize_target_rejects_non_uuid_id() -> None:
    """UUID() raises ValueError on bad input; the helper deliberately wraps
    KeyError/TypeError/AttributeError only — a bare ValueError surfaces
    raw (same shape as Safety's deserialize_binding)."""
    with pytest.raises(ValueError):
        deserialize_target({"kind": "Asset", "id": "not-a-uuid"})


# ---------- CautionRegistered (asset target) ----------


@pytest.mark.unit
def test_caution_registered_event_type_name() -> None:
    event = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category="Wear",
        severity="Caution",
        text="hexapod stalls below 0.5 mm/s",
        workaround="run at 0.6 mm/s",
        tags=frozenset({"low-speed-stall"}),
        authored_by=_AUTHOR_ID,
        expires_at=None,
        propagate_to_children=False,
        parent_id=None,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "CautionRegistered"


@pytest.mark.unit
def test_caution_registered_to_payload_asset_target_tags_sorted() -> None:
    event = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category="Wear",
        severity="Caution",
        text="text",
        workaround="workaround",
        tags=frozenset({"zeta", "alpha", "mu"}),
        authored_by=_AUTHOR_ID,
        expires_at=None,
        propagate_to_children=False,
        parent_id=None,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "caution_id": str(_CAUTION_ID),
        "target": {"kind": "Asset", "id": str(_ASSET_ID)},
        "category": "Wear",
        "severity": "Caution",
        "text": "text",
        "workaround": "workaround",
        "tags": ["alpha", "mu", "zeta"],
        "authored_by": str(_AUTHOR_ID),
        "expires_at": None,
        "propagate_to_children": False,
        "parent_id": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_caution_registered_round_trip_asset_target() -> None:
    original = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category="Calibration",
        severity="Warning",
        text="recalibrate after each downtime",
        workaround="run home script first",
        tags=frozenset({"calib", "downtime"}),
        authored_by=_AUTHOR_ID,
        expires_at=None,
        propagate_to_children=False,
        parent_id=None,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("CautionRegistered", to_payload(original)))
    assert rebuilt == original


@pytest.mark.unit
def test_caution_registered_round_trip_procedure_target_with_expires_at() -> None:
    expires = datetime(2026, 12, 31, tzinfo=UTC)
    original = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=ProcedureTarget(procedure_id=_PROCEDURE_ID),
        category="ProcedureGotcha",
        severity="Notice",
        text="skip step 4 on Tuesdays",
        workaround="manual override at step 5",
        tags=frozenset(),
        authored_by=_AUTHOR_ID,
        expires_at=expires,
        propagate_to_children=True,
        parent_id=None,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("CautionRegistered", to_payload(original)))
    assert rebuilt == original


@pytest.mark.unit
def test_caution_registered_round_trip_with_parent_id() -> None:
    parent_id = UUID("01900000-0000-7000-8000-00000000b999")
    original = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category="Wear",
        severity="Caution",
        text="updated text",
        workaround="updated workaround",
        tags=frozenset({"v2"}),
        authored_by=_AUTHOR_ID,
        expires_at=None,
        propagate_to_children=False,
        parent_id=parent_id,
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("CautionRegistered", to_payload(original)))
    assert rebuilt == original
    assert rebuilt.parent_id == parent_id  # type: ignore[union-attr]


# ---------- CautionSuperseded ----------


@pytest.mark.unit
def test_caution_superseded_event_type_name() -> None:
    event = CautionSuperseded(
        caution_id=_CAUTION_ID,
        superseded_by_caution_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "CautionSuperseded"


@pytest.mark.unit
def test_caution_superseded_round_trip() -> None:
    by_id = UUID("01900000-0000-7000-8000-00000000c001")
    original = CautionSuperseded(
        caution_id=_CAUTION_ID,
        superseded_by_caution_id=by_id,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert payload == {
        "caution_id": str(_CAUTION_ID),
        "superseded_by_caution_id": str(by_id),
        "occurred_at": _NOW.isoformat(),
    }
    rebuilt = from_stored(_stored("CautionSuperseded", payload))
    assert rebuilt == original


# ---------- CautionRetired ----------


@pytest.mark.unit
def test_caution_retired_event_type_name() -> None:
    event = CautionRetired(
        caution_id=_CAUTION_ID,
        reason="Resolved",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "CautionRetired"


@pytest.mark.unit
@pytest.mark.parametrize("reason", ["Resolved", "NoLongerApplies", "WrongTarget"])
def test_caution_retired_round_trip(reason: str) -> None:
    original = CautionRetired(
        caution_id=_CAUTION_ID,
        reason=reason,
        occurred_at=_NOW,
    )
    payload = to_payload(original)
    assert payload == {
        "caution_id": str(_CAUTION_ID),
        "reason": reason,
        "occurred_at": _NOW.isoformat(),
    }
    rebuilt = from_stored(_stored("CautionRetired", payload))
    assert rebuilt == original


# ---------- from_stored unknown event_type ----------


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown CautionEvent event_type"):
        from_stored(_stored("ImaginaryEvent", {"foo": "bar"}))


# ---------- Malformed-payload defensive arms ----------
#
# `from_stored` wraps each event-type constructor in
# `try/except (KeyError, TypeError, AttributeError) -> raise ValueError`.
# Schema-drift insurance: a corrupted event row (older producer's payload
# diverged from the current evolver's expectations) fails loud at the
# evolver instead of crashing with a raw KeyError deep in the load path.


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    ["CautionRegistered", "CautionSuperseded", "CautionRetired"],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """Empty payload triggers KeyError on the first required field lookup;
    the wrapping `except` surfaces a ValueError tagged with the event_type."""
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(_stored(event_type, {}))


# ---------- Defensive payload helpers used inside CautionRegistered ----------


@pytest.mark.unit
def test_caution_registered_payload_carries_target_dict_shape() -> None:
    """Pin the on-wire shape of the embedded target so consumers don't drift."""
    event = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=ProcedureTarget(procedure_id=_PROCEDURE_ID),
        category="ProcedureGotcha",
        severity="Notice",
        text="text",
        workaround="workaround",
        tags=frozenset(),
        authored_by=_AUTHOR_ID,
        expires_at=None,
        propagate_to_children=False,
        parent_id=None,
        occurred_at=_NOW,
    )
    payload: dict[str, Any] = to_payload(event)
    assert payload["target"] == {"kind": "Procedure", "id": str(_PROCEDURE_ID)}
