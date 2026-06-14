"""Unit tests for the Asset aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierRemoved,
    AssetDecommissioned,
    AssetDegraded,
    AssetFamilyAdded,
    AssetFamilyRemoved,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetMaintenanceExited,
    AssetOwnerAdded,
    AssetOwnerRemoved,
    AssetPortAdded,
    AssetPortRemoved,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetSettingsUpdated,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.asset.state import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell — only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Asset",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
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
def test_event_type_name_returns_class_name() -> None:
    event = AssetRegistered(
        asset_id=uuid4(),
        name="APS-2BM",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    assert event_type_name(event) == "AssetRegistered"


@pytest.mark.unit
def test_to_payload_serializes_asset_registered_with_parent() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    event = AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        tier="Unit",
        parent_id=parent_id,
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "name": "APS-2BM",
        "tier": "Unit",
        "parent_id": str(parent_id),
        "occurred_at": _NOW.isoformat(),
        "commissioned_by": str(_TEST_ACTOR_ID),
    }


@pytest.mark.unit
def test_to_payload_serializes_asset_registered_with_null_parent() -> None:
    """Enterprise-level Assets have parent_id=None; the payload
    serializes it as JSON null. Pinned because the round-trip must
    handle Optional UUIDs cleanly."""
    asset_id = uuid4()
    event = AssetRegistered(
        asset_id=asset_id,
        name="ANL",
        tier="Unit",
        parent_id=None,
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["parent_id"] is None
    assert payload["tier"] == "Unit"


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_parent() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "APS-2BM",
            "tier": "Unit",
            "parent_id": str(parent_id),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        tier="Unit",
        parent_id=parent_id,
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_null_parent() -> None:
    """Enterprise root: payload's parent_id is JSON null → Python None."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "ANL",
            "tier": "Unit",
            "parent_id": None,
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.parent_id is None
    assert rebuilt.tier == "Unit"


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_parent() -> None:
    """Round-trip safety net for the typical (non-root) case."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="Eiger-2X-9M",
        tier="Device",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_without_parent() -> None:
    """Round-trip safety net for Enterprise roots (parent_id=None)."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="ANL",
        tier="Unit",
        parent_id=None,
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_omits_drawing_key_when_drawing_is_none() -> None:
    """Additive-payload pattern: legacy AssetRegistered shape (no drawing)
    must serialize without the key, so existing stream readers can't
    accidentally observe a None value where they previously saw the key
    missing."""
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert "drawing" not in payload


@pytest.mark.unit
def test_to_payload_includes_drawing_block_when_set() -> None:
    event = AssetRegistered(
        asset_id=uuid4(),
        name="Microscope-2BM-A",
        tier="Component",
        parent_id=uuid4(),
        occurred_at=_NOW,
        drawing=Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A"),
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["drawing"] == {"system": "ICMS", "number": "P4105", "revision": "A"}


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_drawing() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Microscope-2BM-A",
            "tier": "Component",
            "parent_id": str(parent_id),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
            "drawing": {"system": "EDMS", "number": "9001", "revision": None},
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRegistered(
        asset_id=asset_id,
        name="Microscope-2BM-A",
        tier="Component",
        parent_id=parent_id,
        occurred_at=_NOW,
        drawing=Drawing(system=DrawingSystem.EDMS, number="9001", revision=None),
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_from_stored_folds_legacy_payload_without_drawing_to_none() -> None:
    """Backward-compat pin: existing AssetRegistered events written before
    the drawing widen had no drawing key; they MUST fold to drawing=None
    without raising."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Pre-widen Asset",
            "tier": "Unit",
            "parent_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.drawing is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_without_drawing_explicit() -> None:
    """Pin the omit-then-rebuild path: drawing=None survives the
    serialize+deserialize round-trip and emerges as drawing=None
    (not as a missing attribute or something else)."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="No-Drawing Asset",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.drawing is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_drawing() -> None:
    original = AssetRegistered(
        asset_id=uuid4(),
        name="Microscope-2BM-A",
        tier="Component",
        parent_id=uuid4(),
        occurred_at=_NOW,
        drawing=Drawing(system=DrawingSystem.DOI, number="10.5281/zenodo.X", revision="v2"),
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetRegistered.model_id ----------


@pytest.mark.unit
def test_to_payload_omits_model_id_key_when_model_id_is_none() -> None:
    """Omit-when-None convention (Lock G): legacy AssetRegistered shape
    (no model_id) must serialize without the key so existing stream
    readers can't accidentally observe a None value where they
    previously saw the key missing. Mirrors the drawing precedent."""
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert "model_id" not in payload


@pytest.mark.unit
def test_to_payload_includes_model_id_when_set() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    model_id = uuid4()
    event = AssetRegistered(
        asset_id=asset_id,
        name="Microscope-2BM-A",
        tier="Component",
        parent_id=parent_id,
        occurred_at=_NOW,
        model_id=model_id,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["model_id"] == str(model_id)


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_model_id() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    model_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Microscope-2BM-A",
            "tier": "Component",
            "parent_id": str(parent_id),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
            "model_id": str(model_id),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRegistered(
        asset_id=asset_id,
        name="Microscope-2BM-A",
        tier="Component",
        parent_id=parent_id,
        occurred_at=_NOW,
        model_id=model_id,
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_from_stored_folds_legacy_payload_without_model_id_to_none() -> None:
    """Backward-compat pin: existing AssetRegistered events written before
    the model_id widen had no model_id key; they MUST fold to
    model_id=None without raising. Mirrors the drawing legacy-fold
    precedent."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Pre-widen Asset",
            "tier": "Unit",
            "parent_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.model_id is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_without_model_id_explicit() -> None:
    """Pin the omit-then-rebuild path: model_id=None survives the
    serialize+deserialize round-trip and emerges as model_id=None
    (not as a missing attribute or something else)."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="No-Model Asset",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.model_id is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_model_id() -> None:
    original = AssetRegistered(
        asset_id=uuid4(),
        name="Microscope-2BM-A",
        tier="Component",
        parent_id=uuid4(),
        occurred_at=_NOW,
        model_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_drawing_and_model_id() -> None:
    """Both additive fields set: the two omit-when-None blocks must
    compose cleanly and the round-trip preserves both."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="Microscope-2BM-A",
        tier="Component",
        parent_id=uuid4(),
        occurred_at=_NOW,
        drawing=Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A"),
        model_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetRegistered.controller_id ----------


@pytest.mark.unit
def test_to_payload_omits_controller_id_key_when_controller_id_is_none() -> None:
    """Omit-when-None convention: legacy AssetRegistered shape (no
    controller_id) must serialize without the key so existing stream
    readers can't accidentally observe a JSON null where they
    previously saw the key missing. Mirrors the model_id / drawing
    precedent."""
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert "controller_id" not in payload


@pytest.mark.unit
def test_to_payload_includes_controller_id_when_set() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    controller_id = uuid4()
    event = AssetRegistered(
        asset_id=asset_id,
        name="Rotary",
        tier="Device",
        parent_id=parent_id,
        occurred_at=_NOW,
        controller_id=controller_id,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["controller_id"] == str(controller_id)


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_controller_id() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    controller_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Rotary",
            "tier": "Device",
            "parent_id": str(parent_id),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
            "controller_id": str(controller_id),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRegistered(
        asset_id=asset_id,
        name="Rotary",
        tier="Device",
        parent_id=parent_id,
        occurred_at=_NOW,
        controller_id=controller_id,
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_from_stored_folds_legacy_payload_without_controller_id_to_none() -> None:
    """Backward-compat pin: existing AssetRegistered events written
    before the controller_id widen had no controller_id key; they MUST
    fold to controller_id=None without raising. Mirrors the model_id
    legacy-fold precedent."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Pre-widen Asset",
            "tier": "Unit",
            "parent_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.controller_id is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_controller_id() -> None:
    original = AssetRegistered(
        asset_id=uuid4(),
        name="Rotary",
        tier="Device",
        parent_id=uuid4(),
        occurred_at=_NOW,
        controller_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetRegistered.located_in_enclosure_id ----------


@pytest.mark.unit
def test_to_payload_omits_located_in_enclosure_id_key_when_none() -> None:
    """Omit-when-None convention: legacy AssetRegistered shape (no
    located_in_enclosure_id) must serialize without the key so existing
    stream readers can't accidentally observe a JSON null where they
    previously saw the key missing. Mirrors the controller_id / model_id
    precedent."""
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert "located_in_enclosure_id" not in payload


@pytest.mark.unit
def test_to_payload_includes_located_in_enclosure_id_when_set() -> None:
    located_in_enclosure_id = uuid4()
    event = AssetRegistered(
        asset_id=uuid4(),
        name="Aerotech_ABRS_rotary",
        tier="Device",
        parent_id=uuid4(),
        occurred_at=_NOW,
        located_in_enclosure_id=located_in_enclosure_id,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["located_in_enclosure_id"] == str(located_in_enclosure_id)


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_located_in_enclosure_id() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    located_in_enclosure_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Aerotech_ABRS_rotary",
            "tier": "Device",
            "parent_id": str(parent_id),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
            "located_in_enclosure_id": str(located_in_enclosure_id),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRegistered(
        asset_id=asset_id,
        name="Aerotech_ABRS_rotary",
        tier="Device",
        parent_id=parent_id,
        occurred_at=_NOW,
        located_in_enclosure_id=located_in_enclosure_id,
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_from_stored_folds_legacy_payload_without_located_in_enclosure_id_to_none() -> None:
    """Backward-compat pin: existing AssetRegistered events written
    before the located_in_enclosure_id widen had no such key; they MUST
    fold to located_in_enclosure_id=None without raising. Mirrors the
    controller_id legacy-fold precedent."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Pre-widen Asset",
            "tier": "Unit",
            "parent_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.located_in_enclosure_id is None


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_located_in_enclosure_id() -> None:
    original = AssetRegistered(
        asset_id=uuid4(),
        name="Aerotech_ABRS_rotary",
        tier="Device",
        parent_id=uuid4(),
        occurred_at=_NOW,
        located_in_enclosure_id=uuid4(),
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("FamilyDefined", {})
    with pytest.raises(ValueError, match="Unknown AssetEvent event_type"):
        from_stored(stored)


# ---------- AssetActivated ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_activated_class_name() -> None:
    event = AssetActivated(asset_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetActivated"


@pytest.mark.unit
def test_to_payload_serializes_asset_activated_to_primitives() -> None:
    """Lifecycle NOT in payload — event TYPE encodes the state change.
    Pinned because adding a `lifecycle` field to the payload (for example, to
    support a generic 'set lifecycle' command later) is an additive
    change that must be deliberate."""
    asset_id = uuid4()
    event = AssetActivated(asset_id=asset_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_activated() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetActivated",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetActivated(asset_id=asset_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_activated() -> None:
    original = AssetActivated(asset_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetActivated", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetDecommissioned ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_decommissioned_class_name() -> None:
    event = AssetDecommissioned(
        asset_id=uuid4(), occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
    )
    assert event_type_name(event) == "AssetDecommissioned"


@pytest.mark.unit
def test_to_payload_serializes_asset_decommissioned_to_primitives() -> None:
    """Lifecycle NOT in payload — multi-source-to-single-target
    transitions still encode source state via the decider's guard, not
    the event payload (no `from_lifecycle` field). Same convention as
    Subject's SubjectRemoved (also multi-source-to-single-target)."""
    asset_id = uuid4()
    event = AssetDecommissioned(
        asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
    )
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
        "decommissioned_by": str(_TEST_ACTOR_ID),
    }
    assert "lifecycle" not in payload
    assert "from_lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_decommissioned() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetDecommissioned",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
            "decommissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetDecommissioned(
        asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_decommissioned() -> None:
    original = AssetDecommissioned(
        asset_id=uuid4(), occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
    )
    stored = _stored("AssetDecommissioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetRelocated ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_relocated_class_name() -> None:
    event = AssetRelocated(
        asset_id=uuid4(),
        from_parent_id=uuid4(),
        to_parent_id=uuid4(),
        reason="site reorganization",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "AssetRelocated"


@pytest.mark.unit
def test_to_payload_serializes_asset_relocated_with_both_parents_and_reason() -> None:
    """First event in the codebase whose payload carries source AND
    target state. Pinned because adding a `lifecycle` or other field
    is an additive change that must be deliberate, AND because both
    parent UUIDs must serialize as strings (not raw UUID instances)."""
    asset_id = uuid4()
    from_parent_id = uuid4()
    to_parent_id = uuid4()
    event = AssetRelocated(
        asset_id=asset_id,
        from_parent_id=from_parent_id,
        to_parent_id=to_parent_id,
        reason="moved from storage to BL2-IBP",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "from_parent_id": str(from_parent_id),
        "to_parent_id": str(to_parent_id),
        "reason": "moved from storage to BL2-IBP",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_relocated() -> None:
    asset_id = uuid4()
    from_parent_id = uuid4()
    to_parent_id = uuid4()
    stored = _stored(
        "AssetRelocated",
        {
            "asset_id": str(asset_id),
            "from_parent_id": str(from_parent_id),
            "to_parent_id": str(to_parent_id),
            "reason": "site reorganization 2026-Q3",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRelocated(
        asset_id=asset_id,
        from_parent_id=from_parent_id,
        to_parent_id=to_parent_id,
        reason="site reorganization 2026-Q3",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_relocated() -> None:
    original = AssetRelocated(
        asset_id=uuid4(),
        from_parent_id=uuid4(),
        to_parent_id=uuid4(),
        reason="commissioning move",
        occurred_at=_NOW,
    )
    stored = _stored("AssetRelocated", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetMaintenanceEntered ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_maintenance_entered_class_name() -> None:
    event = AssetMaintenanceEntered(asset_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetMaintenanceEntered"


@pytest.mark.unit
def test_to_payload_serializes_asset_maintenance_entered_to_primitives() -> None:
    """Lifecycle NOT in payload — event TYPE encodes the state change.
    Same convention as AssetActivated / AssetDecommissioned."""
    asset_id = uuid4()
    event = AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_maintenance_entered() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetMaintenanceEntered",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_maintenance_entered() -> None:
    original = AssetMaintenanceEntered(asset_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetMaintenanceEntered", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetMaintenanceExited ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_maintenance_exited_class_name() -> None:
    event = AssetMaintenanceExited(asset_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetMaintenanceExited"


@pytest.mark.unit
def test_to_payload_serializes_asset_maintenance_exited_to_primitives() -> None:
    asset_id = uuid4()
    event = AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_maintenance_exited() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetMaintenanceExited",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_maintenance_exited() -> None:
    original = AssetMaintenanceExited(asset_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetMaintenanceExited", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetFamilyAdded ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_capability_added_class_name() -> None:
    event = AssetFamilyAdded(asset_id=uuid4(), family_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetFamilyAdded"


@pytest.mark.unit
def test_to_payload_serializes_asset_capability_added_to_primitives() -> None:
    asset_id = uuid4()
    family_id = uuid4()
    event = AssetFamilyAdded(asset_id=asset_id, family_id=family_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "family_id": str(family_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_capability_added() -> None:
    asset_id = uuid4()
    family_id = uuid4()
    stored = _stored(
        "AssetFamilyAdded",
        {
            "asset_id": str(asset_id),
            "family_id": str(family_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetFamilyAdded(asset_id=asset_id, family_id=family_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_capability_added() -> None:
    original = AssetFamilyAdded(asset_id=uuid4(), family_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetFamilyAdded", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetFamilyRemoved ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_capability_removed_class_name() -> None:
    event = AssetFamilyRemoved(asset_id=uuid4(), family_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetFamilyRemoved"


@pytest.mark.unit
def test_to_payload_serializes_asset_capability_removed_to_primitives() -> None:
    asset_id = uuid4()
    family_id = uuid4()
    event = AssetFamilyRemoved(asset_id=asset_id, family_id=family_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "family_id": str(family_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_capability_removed() -> None:
    asset_id = uuid4()
    family_id = uuid4()
    stored = _stored(
        "AssetFamilyRemoved",
        {
            "asset_id": str(asset_id),
            "family_id": str(family_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetFamilyRemoved(asset_id=asset_id, family_id=family_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_capability_removed() -> None:
    original = AssetFamilyRemoved(asset_id=uuid4(), family_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetFamilyRemoved", to_payload(original))
    assert from_stored(stored) == original


# ---------- condition-transition events ----------


@pytest.mark.unit
def test_to_payload_serializes_asset_degraded() -> None:
    asset_id = uuid4()
    event = AssetDegraded(asset_id=asset_id, reason="hot pixel", occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "reason": "hot pixel",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_degraded() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetDegraded",
        {
            "asset_id": str(asset_id),
            "reason": "hot pixel",
            "occurred_at": _NOW.isoformat(),
        },
    )
    assert from_stored(stored) == AssetDegraded(
        asset_id=asset_id, reason="hot pixel", occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_degraded() -> None:
    original = AssetDegraded(asset_id=uuid4(), reason="hot pixel", occurred_at=_NOW)
    stored = _stored("AssetDegraded", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_asset_faulted() -> None:
    asset_id = uuid4()
    event = AssetFaulted(asset_id=asset_id, reason="vacuum pump seized", occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "reason": "vacuum pump seized",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_faulted() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetFaulted",
        {
            "asset_id": str(asset_id),
            "reason": "vacuum pump seized",
            "occurred_at": _NOW.isoformat(),
        },
    )
    assert from_stored(stored) == AssetFaulted(
        asset_id=asset_id, reason="vacuum pump seized", occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_faulted() -> None:
    original = AssetFaulted(asset_id=uuid4(), reason="seized", occurred_at=_NOW)
    stored = _stored("AssetFaulted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_asset_restored() -> None:
    asset_id = uuid4()
    event = AssetRestored(asset_id=asset_id, reason="replaced flat cable", occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "reason": "replaced flat cable",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_restored() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetRestored",
        {
            "asset_id": str(asset_id),
            "reason": "replaced flat cable",
            "occurred_at": _NOW.isoformat(),
        },
    )
    assert from_stored(stored) == AssetRestored(
        asset_id=asset_id, reason="replaced flat cable", occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_restored() -> None:
    original = AssetRestored(asset_id=uuid4(), reason="repaired", occurred_at=_NOW)
    stored = _stored("AssetRestored", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_event_type_name_returns_class_name_for_condition_events() -> None:
    asset_id = uuid4()
    assert event_type_name(AssetDegraded(asset_id=asset_id, reason="r", occurred_at=_NOW)) == (
        "AssetDegraded"
    )
    assert event_type_name(AssetFaulted(asset_id=asset_id, reason="r", occurred_at=_NOW)) == (
        "AssetFaulted"
    )
    assert event_type_name(AssetRestored(asset_id=asset_id, reason="r", occurred_at=_NOW)) == (
        "AssetRestored"
    )


# ---------- AssetSettingsUpdated ----------


@pytest.mark.unit
def test_to_payload_serializes_asset_settings_updated() -> None:
    asset_id = uuid4()
    settings = {"energy": 30, "filter": "Cu"}
    event = AssetSettingsUpdated(asset_id=asset_id, settings=settings, occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "settings": {"energy": 30, "filter": "Cu"},
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_asset_settings_updated_with_empty_dict() -> None:
    """Empty settings (full cleanup case) round-trips correctly."""
    asset_id = uuid4()
    event = AssetSettingsUpdated(asset_id=asset_id, settings={}, occurred_at=_NOW)
    assert to_payload(event)["settings"] == {}


@pytest.mark.unit
def test_from_stored_rebuilds_asset_settings_updated() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetSettingsUpdated",
        {
            "asset_id": str(asset_id),
            "settings": {"energy": 30},
            "occurred_at": _NOW.isoformat(),
        },
    )
    assert from_stored(stored) == AssetSettingsUpdated(
        asset_id=asset_id, settings={"energy": 30}, occurred_at=_NOW
    )


@pytest.mark.unit
def test_from_stored_tolerates_missing_settings_key_for_additive_evolution() -> None:
    """Pre-5g-c stored events without the settings key fold to {}.
    Additive-state pattern."""
    asset_id = uuid4()
    stored = _stored(
        "AssetSettingsUpdated",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
            # settings key intentionally absent
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetSettingsUpdated)
    assert rebuilt.settings == {}


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_settings_updated() -> None:
    original = AssetSettingsUpdated(
        asset_id=uuid4(),
        settings={"energy": 30, "filter": "Cu", "nested": {"x": 1}},
        occurred_at=_NOW,
    )
    stored = _stored("AssetSettingsUpdated", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_event_type_name_for_asset_settings_updated() -> None:
    event = AssetSettingsUpdated(asset_id=uuid4(), settings={}, occurred_at=_NOW)
    assert event_type_name(event) == "AssetSettingsUpdated"


# ---------- AssetPortAdded / AssetPortRemoved ----------


@pytest.mark.unit
def test_to_payload_serializes_asset_port_added() -> None:
    asset_id = uuid4()
    event = AssetPortAdded(
        asset_id=asset_id,
        port_name="trigger_in",
        direction="Input",
        signal_type="TTL",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "port_name": "trigger_in",
        "direction": "Input",
        "signal_type": "TTL",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_port_added() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetPortAdded",
        {
            "asset_id": str(asset_id),
            "port_name": "trigger_in",
            "direction": "Input",
            "signal_type": "TTL",
            "occurred_at": _NOW.isoformat(),
        },
    )
    assert from_stored(stored) == AssetPortAdded(
        asset_id=asset_id,
        port_name="trigger_in",
        direction="Input",
        signal_type="TTL",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_round_trip_for_asset_port_added() -> None:
    original = AssetPortAdded(
        asset_id=uuid4(),
        port_name="encoder_a",
        direction="Output",
        signal_type="LVDS",
        occurred_at=_NOW,
    )
    stored = _stored("AssetPortAdded", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_asset_port_removed() -> None:
    asset_id = uuid4()
    event = AssetPortRemoved(asset_id=asset_id, port_name="sync_clock", occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "port_name": "sync_clock",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_for_asset_port_removed() -> None:
    original = AssetPortRemoved(asset_id=uuid4(), port_name="x", occurred_at=_NOW)
    stored = _stored("AssetPortRemoved", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_event_type_name_for_port_events() -> None:
    asset_id = uuid4()
    added = AssetPortAdded(
        asset_id=asset_id, port_name="x", direction="Input", signal_type="TTL", occurred_at=_NOW
    )
    removed = AssetPortRemoved(asset_id=asset_id, port_name="x", occurred_at=_NOW)
    assert event_type_name(added) == "AssetPortAdded"
    assert event_type_name(removed) == "AssetPortRemoved"


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "AssetRegistered",
        "AssetActivated",
        "AssetDecommissioned",
        "AssetRelocated",
        "AssetMaintenanceEntered",
        "AssetMaintenanceExited",
        "AssetFamilyAdded",
        "AssetFamilyRemoved",
        "AssetDegraded",
        "AssetFaulted",
        "AssetRestored",
        "AssetSettingsUpdated",
        "AssetPortAdded",
        "AssetPortRemoved",
        "AssetAlternateIdentifierAdded",
        "AssetAlternateIdentifierRemoved",
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


# ---------- AssetRegistered.alternate_identifiers ----------


_SAMPLE_ALT_ID_A = AlternateIdentifier(
    kind=AlternateIdentifierKind.SERIAL_NUMBER, value="12345-ABC"
)
_SAMPLE_ALT_ID_B = AlternateIdentifier(
    kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-2BM-CAM-001"
)


@pytest.mark.unit
def test_to_payload_omits_alternate_identifiers_when_empty() -> None:
    """Omit-when-empty convention (Lock D): legacy AssetRegistered shape
    (no alternate_identifiers) must serialize without the key so
    existing stream readers can't accidentally observe an empty list
    where the key was previously absent. Mirrors the drawing /
    model_id precedents."""
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert "alternate_identifiers" not in payload


@pytest.mark.unit
def test_to_payload_includes_alternate_identifiers_when_set() -> None:
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Component",
        parent_id=uuid4(),
        occurred_at=_NOW,
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A}),
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["alternate_identifiers"] == [
        {"kind": "SerialNumber", "value": "12345-ABC"},
    ]


@pytest.mark.unit
def test_to_payload_emits_alternate_identifiers_sorted_for_stable_bytes() -> None:
    """Payload bytes must be deterministic across runs even though
    frozenset iteration is not. Sorted on (kind, value) gives the
    same JSON for the same VO set, which matters for any future
    signing / content-addressed slice."""
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Component",
        parent_id=uuid4(),
        occurred_at=_NOW,
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_B, _SAMPLE_ALT_ID_A}),
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["alternate_identifiers"] == [
        {"kind": "InventoryNumber", "value": "APS-2BM-CAM-001"},
        {"kind": "SerialNumber", "value": "12345-ABC"},
    ]


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_alternate_identifiers() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "X",
            "tier": "Component",
            "parent_id": str(parent_id),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
            "alternate_identifiers": [
                {"kind": "SerialNumber", "value": "12345-ABC"},
                {"kind": "InventoryNumber", "value": "APS-2BM-CAM-001"},
            ],
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRegistered(
        asset_id=asset_id,
        name="X",
        tier="Component",
        parent_id=parent_id,
        occurred_at=_NOW,
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B}),
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_from_stored_folds_legacy_payload_without_alternate_identifiers_to_empty() -> None:
    """Backward-compat pin: existing AssetRegistered events written
    before the alternate_identifiers widen had no key; they MUST fold
    to an empty frozenset without raising. Mirrors the drawing /
    model_id legacy-fold precedents."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "Pre-widen Asset",
            "tier": "Unit",
            "parent_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.alternate_identifiers == frozenset()


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_without_alternate_identifiers_explicit() -> None:
    """Pin the omit-then-rebuild path: alternate_identifiers=empty
    frozenset survives the round-trip and emerges as the empty
    frozenset (not as a missing attribute or list)."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="No-AltIds Asset",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.alternate_identifiers == frozenset()


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_alternate_identifiers() -> None:
    original = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Component",
        parent_id=uuid4(),
        occurred_at=_NOW,
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B}),
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetAlternateIdentifierAdded ----------


@pytest.mark.unit
def test_event_type_name_returns_alternate_identifier_added_class_name() -> None:
    event = AssetAlternateIdentifierAdded(
        asset_id=uuid4(), alternate_identifier=_SAMPLE_ALT_ID_A, occurred_at=_NOW
    )
    assert event_type_name(event) == "AssetAlternateIdentifierAdded"


@pytest.mark.unit
def test_to_payload_serializes_alternate_identifier_added() -> None:
    asset_id = uuid4()
    event = AssetAlternateIdentifierAdded(
        asset_id=asset_id,
        alternate_identifier=_SAMPLE_ALT_ID_A,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "alternate_identifier": {"kind": "SerialNumber", "value": "12345-ABC"},
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_alternate_identifier_added() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetAlternateIdentifierAdded",
        {
            "asset_id": str(asset_id),
            "alternate_identifier": {"kind": "SerialNumber", "value": "12345-ABC"},
            "occurred_at": _NOW.isoformat(),
        },
    )
    assert from_stored(stored) == AssetAlternateIdentifierAdded(
        asset_id=asset_id,
        alternate_identifier=_SAMPLE_ALT_ID_A,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_round_trip_for_alternate_identifier_added() -> None:
    original = AssetAlternateIdentifierAdded(
        asset_id=uuid4(),
        alternate_identifier=_SAMPLE_ALT_ID_B,
        occurred_at=_NOW,
    )
    stored = _stored("AssetAlternateIdentifierAdded", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetAlternateIdentifierRemoved ----------


@pytest.mark.unit
def test_event_type_name_returns_alternate_identifier_removed_class_name() -> None:
    event = AssetAlternateIdentifierRemoved(
        asset_id=uuid4(), alternate_identifier=_SAMPLE_ALT_ID_A, occurred_at=_NOW
    )
    assert event_type_name(event) == "AssetAlternateIdentifierRemoved"


@pytest.mark.unit
def test_to_payload_serializes_alternate_identifier_removed() -> None:
    asset_id = uuid4()
    event = AssetAlternateIdentifierRemoved(
        asset_id=asset_id,
        alternate_identifier=_SAMPLE_ALT_ID_B,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "alternate_identifier": {"kind": "InventoryNumber", "value": "APS-2BM-CAM-001"},
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_alternate_identifier_removed() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetAlternateIdentifierRemoved",
        {
            "asset_id": str(asset_id),
            "alternate_identifier": {"kind": "InventoryNumber", "value": "APS-2BM-CAM-001"},
            "occurred_at": _NOW.isoformat(),
        },
    )
    assert from_stored(stored) == AssetAlternateIdentifierRemoved(
        asset_id=asset_id,
        alternate_identifier=_SAMPLE_ALT_ID_B,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_round_trip_for_alternate_identifier_removed() -> None:
    original = AssetAlternateIdentifierRemoved(
        asset_id=uuid4(),
        alternate_identifier=_SAMPLE_ALT_ID_A,
        occurred_at=_NOW,
    )
    stored = _stored("AssetAlternateIdentifierRemoved", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_alternate_identifier_kind() -> None:
    """An unknown `kind` payload value can't reconstruct the closed
    StrEnum and must surface as a tagged Malformed error rather than a
    bare ValueError from the enum constructor."""
    stored = _stored(
        "AssetAlternateIdentifierAdded",
        {
            "asset_id": str(uuid4()),
            "alternate_identifier": {"kind": "Unknown", "value": "x"},
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetAlternateIdentifierAdded payload"):
        from_stored(stored)


_HZB_OWNER = AssetOwner(
    name=AssetOwnerName("HZB"),
    contact=AssetOwnerContact("ops@helmholtz-berlin.de"),
    identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
    identifier_type=AssetOwnerIdentifierType("ROR"),
)


@pytest.mark.unit
def test_to_payload_serializes_asset_registered_with_owners() -> None:
    asset_id = uuid4()
    event = AssetRegistered(
        asset_id=asset_id,
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        owners=frozenset({_HZB_OWNER}),
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert payload["owners"] == [
        {
            "name": "HZB",
            "contact": "ops@helmholtz-berlin.de",
            "identifier": "https://ror.org/02aj13c28",
            "identifier_type": "ROR",
        }
    ]


@pytest.mark.unit
def test_to_payload_omits_owners_when_empty() -> None:
    """Mirror of the alternate_identifiers omit-when-empty convention:
    legacy AssetRegistered events had no `owners` key; preserve that
    wire shape so stream readers can't observe an empty list where the
    key was previously absent."""
    event = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    assert "owners" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_without_owners_key_defaults_to_empty() -> None:
    """Replay back-compat: a pre-Slice-D AssetRegistered payload with
    no `owners` key folds to `owners=frozenset()` (Lock 1)."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "X",
            "tier": "Unit",
            "parent_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.owners == frozenset()


@pytest.mark.unit
def test_round_trip_for_asset_registered_with_owners() -> None:
    original = AssetRegistered(
        asset_id=uuid4(),
        name="X",
        tier="Unit",
        parent_id=uuid4(),
        occurred_at=_NOW,
        owners=frozenset({_HZB_OWNER}),
        commissioned_by=_TEST_ACTOR_ID,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_owner_added() -> None:
    asset_id = uuid4()
    event = AssetOwnerAdded(asset_id=asset_id, owner=_HZB_OWNER, occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "owner": {
            "name": "HZB",
            "contact": "ops@helmholtz-berlin.de",
            "identifier": "https://ror.org/02aj13c28",
            "identifier_type": "ROR",
        },
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_for_owner_added() -> None:
    original = AssetOwnerAdded(asset_id=uuid4(), owner=_HZB_OWNER, occurred_at=_NOW)
    stored = _stored("AssetOwnerAdded", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_owner_removed() -> None:
    asset_id = uuid4()
    event = AssetOwnerRemoved(asset_id=asset_id, owner_name=AssetOwnerName("HZB"), occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "owner_name": "HZB",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_for_owner_removed() -> None:
    original = AssetOwnerRemoved(
        asset_id=uuid4(), owner_name=AssetOwnerName("HZB"), occurred_at=_NOW
    )
    stored = _stored("AssetOwnerRemoved", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_owner_added_with_invalid_pairing_raises_malformed() -> None:
    """Malformed AssetOwnerAdded payloads (pairing-invariant violation)
    surface as a Malformed* ValueError wrap, not a bare
    InvalidAssetOwnerIdentifierPairingError. The extra=(ValueError,)
    wrap absorbs the per-VO subclass for stream-decoding hygiene."""
    stored = _stored(
        "AssetOwnerAdded",
        {
            "asset_id": str(uuid4()),
            "owner": {
                "name": "HZB",
                "contact": None,
                "identifier": "02aj13c28",
                "identifier_type": None,  # pairing violation
            },
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetOwnerAdded payload"):
        from_stored(stored)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_type", "extra_payload"),
    [
        ("AssetRegistered", {"owners": [{"name": "   "}]}),  # malformed owner
    ],
)
def test_replay_asset_registered_back_compat_paths(
    event_type: str, extra_payload: dict[str, object]
) -> None:
    """Parametrized entry point per Section 9.4 of the design memo. The
    canonical case (no `owners` key -> empty frozenset) is covered by
    `test_from_stored_rebuilds_asset_registered_without_owners_key_defaults_to_empty`
    above; this matrix asserts that malformed owner shapes wrap to the
    canonical Malformed* error rather than leaking the raw VO failure."""
    base_payload: dict[str, object] = {
        "asset_id": str(uuid4()),
        "name": "X",
        "tier": "Unit",
        "parent_id": str(uuid4()),
        "occurred_at": _NOW.isoformat(),
    }
    payload = {**base_payload, **extra_payload}
    stored = _stored(event_type, payload)
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(stored)
