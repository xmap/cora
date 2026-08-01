"""Unit tests for the Plan aggregate's event (de)serialization helpers.

Plan event payloads are richer than Method / Practice / Family
because of the audit snapshots (gate-review Q4): `method_id`,
`method_needed_family_ids_snapshot`, and `asset_families_snapshot`.
These tests pin the deterministic-ordering invariants required for
idempotency-key hashing.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.plan.events import (
    PlanDefaultParametersUpdated,
    PlanDefined,
    PlanDeprecated,
    PlanVersioned,
    PlanWireAdded,
    PlanWireRemoved,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.shared.deprecation import DeprecationReason

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Plan",
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
    event = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=(),
        method_id=uuid4(),
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PlanDefined"


@pytest.mark.unit
def test_to_payload_serializes_plan_defined_to_primitives() -> None:
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    asset_id = uuid4()
    cap_id = uuid4()
    event = PlanDefined(
        plan_id=plan_id,
        name="32-ID FlyScan",
        practice_id=practice_id,
        asset_ids=(asset_id,),
        method_id=method_id,
        method_needed_family_ids_snapshot=(cap_id,),
        asset_families_snapshot={asset_id: (cap_id,)},
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "plan_id": str(plan_id),
        "name": "32-ID FlyScan",
        "practice_id": str(practice_id),
        "asset_ids": [str(asset_id)],
        "method_id": str(method_id),
        "method_needed_family_ids_snapshot": [str(cap_id)],
        "asset_families_snapshot": {str(asset_id): [str(cap_id)]},
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_sorts_asset_ids_for_determinism() -> None:
    """Idempotency-key hashing requires byte-deterministic payloads."""
    a1 = uuid4()
    a2 = uuid4()
    a3 = uuid4()
    forward = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=(a1, a2, a3),
        method_id=uuid4(),
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )
    reverse = PlanDefined(
        plan_id=forward.plan_id,
        name=forward.name,
        practice_id=forward.practice_id,
        asset_ids=(a3, a2, a1),
        method_id=forward.method_id,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )
    assert to_payload(forward)["asset_ids"] == to_payload(reverse)["asset_ids"]
    assert to_payload(forward)["asset_ids"] == sorted(str(a) for a in [a1, a2, a3])


@pytest.mark.unit
def test_to_payload_sorts_method_needed_family_ids_snapshot_for_determinism() -> None:
    c1 = uuid4()
    c2 = uuid4()
    forward = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=(),
        method_id=uuid4(),
        method_needed_family_ids_snapshot=(c1, c2),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )
    reverse = PlanDefined(
        plan_id=forward.plan_id,
        name=forward.name,
        practice_id=forward.practice_id,
        asset_ids=(),
        method_id=forward.method_id,
        method_needed_family_ids_snapshot=(c2, c1),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )
    assert (
        to_payload(forward)["method_needed_family_ids_snapshot"]
        == to_payload(reverse)["method_needed_family_ids_snapshot"]
    )


@pytest.mark.unit
def test_to_payload_sorts_asset_families_snapshot_keys_and_values() -> None:
    """Both outer dict keys (asset_ids) and inner lists (family_ids)
    must be deterministically ordered for idempotency-key hashing."""
    a1 = uuid4()
    a2 = uuid4()
    c1 = uuid4()
    c2 = uuid4()
    snapshot_unsorted = {
        a2: (c2, c1),  # outer: a2 first; inner: c2 first
        a1: (c2, c1),
    }
    event = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=(),
        method_id=uuid4(),
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot=snapshot_unsorted,
        occurred_at=_NOW,
    )
    raw = to_payload(event)["asset_families_snapshot"]
    assert isinstance(raw, dict)
    # pyright doesn't narrow the dict's element types from `dict` alone;
    # cast via list[str] for the keys assertion and skip narrowing values.
    keys: list[str] = list(raw.keys())  # pyright: ignore[reportUnknownArgumentType]
    assert keys == sorted([str(a1), str(a2)])
    for caps in raw.values():  # pyright: ignore[reportUnknownVariableType]
        assert caps == sorted([str(c1), str(c2)])


@pytest.mark.unit
def test_from_stored_rebuilds_plan_defined() -> None:
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    asset_id = uuid4()
    cap_id = uuid4()
    stored = _stored(
        "PlanDefined",
        {
            "plan_id": str(plan_id),
            "name": "32-ID FlyScan",
            "practice_id": str(practice_id),
            "asset_ids": [str(asset_id)],
            "method_id": str(method_id),
            "method_needed_family_ids_snapshot": [str(cap_id)],
            "asset_families_snapshot": {str(asset_id): [str(cap_id)]},
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PlanDefined(
        plan_id=plan_id,
        name="32-ID FlyScan",
        practice_id=practice_id,
        asset_ids=(asset_id,),
        method_id=method_id,
        method_needed_family_ids_snapshot=(cap_id,),
        asset_families_snapshot={asset_id: (cap_id,)},
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net for the full payload shape including snapshots."""
    asset_id = uuid4()
    cap_id = uuid4()
    original = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=(asset_id,),
        method_id=uuid4(),
        method_needed_family_ids_snapshot=(cap_id,),
        asset_families_snapshot={asset_id: (cap_id,)},
        occurred_at=_NOW,
    )
    stored = _stored("PlanDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("PracticeDefined", {})
    with pytest.raises(ValueError, match="Unknown PlanEvent event_type"):
        from_stored(stored)


# ---------- PlanVersioned ----------


@pytest.mark.unit
def test_event_type_name_returns_plan_versioned_class_name() -> None:
    event = PlanVersioned(plan_id=uuid4(), version_tag="v2", occurred_at=_NOW)
    assert event_type_name(event) == "PlanVersioned"


@pytest.mark.unit
def test_to_payload_serializes_plan_versioned_with_version_tag() -> None:
    plan_id = uuid4()
    event = PlanVersioned(plan_id=plan_id, version_tag="2026-Q3", occurred_at=_NOW)
    assert to_payload(event) == {
        "plan_id": str(plan_id),
        "version_tag": "2026-Q3",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_plan_versioned() -> None:
    plan_id = uuid4()
    stored = _stored(
        "PlanVersioned",
        {
            "plan_id": str(plan_id),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_plan_versioned() -> None:
    original = PlanVersioned(plan_id=uuid4(), version_tag="v3", occurred_at=_NOW)
    stored = _stored("PlanVersioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- PlanDeprecated ----------


@pytest.mark.unit
def test_event_type_name_returns_plan_deprecated_class_name() -> None:
    event = PlanDeprecated(reason="Superseded", plan_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "PlanDeprecated"


@pytest.mark.unit
def test_to_payload_serializes_plan_deprecated_to_primitives() -> None:
    """Status NOT in payload — event TYPE encodes the state change."""
    plan_id = uuid4()
    event = PlanDeprecated(reason="Superseded", plan_id=plan_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "plan_id": str(plan_id),
        "reason": "Superseded",
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_plan_deprecated() -> None:
    plan_id = uuid4()
    stored = _stored(
        "PlanDeprecated",
        {
            "plan_id": str(plan_id),
            "reason": "Superseded",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PlanDeprecated(reason="Superseded", plan_id=plan_id, occurred_at=_NOW)


@pytest.mark.unit
@pytest.mark.parametrize("reason", list(DeprecationReason))
def test_to_payload_then_from_stored_round_trips_for_plan_deprecated(
    reason: DeprecationReason,
) -> None:
    """Every member of the closed vocabulary survives the wire, not just the
    common one.

    `Superseded` accounted for every use in the corpus when this was written;
    `Defective` had none, and it is the value the enum exists to make findable.
    A member that failed to round-trip would therefore have been invisible.
    """
    original = PlanDeprecated(reason=reason.value, plan_id=uuid4(), occurred_at=_NOW)
    stored = _stored("PlanDeprecated", to_payload(original))
    assert from_stored(stored) == original
    assert stored.payload["reason"] == reason.value


# ---------- PlanDefaultParametersUpdated ----------


_SAMPLE_DEFAULTS: dict[str, object] = {"energy": 12.0, "exposure": 100}


@pytest.mark.unit
def test_event_type_name_returns_default_parameters_updated_class_name() -> None:
    event = PlanDefaultParametersUpdated(
        plan_id=uuid4(), default_parameters=_SAMPLE_DEFAULTS, occurred_at=_NOW
    )
    assert event_type_name(event) == "PlanDefaultParametersUpdated"


@pytest.mark.unit
def test_to_payload_serializes_default_parameters_updated_with_dict() -> None:
    plan_id = uuid4()
    event = PlanDefaultParametersUpdated(
        plan_id=plan_id, default_parameters=_SAMPLE_DEFAULTS, occurred_at=_NOW
    )
    assert to_payload(event) == {
        "plan_id": str(plan_id),
        "default_parameters": _SAMPLE_DEFAULTS,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_default_parameters_updated_with_empty_dict() -> None:
    """Empty dict is serialized as `{}` (NOT omitted). Pinned because
    the projection's `bool(payload.get("default_parameters"))` test
    relies on the key being present."""
    plan_id = uuid4()
    event = PlanDefaultParametersUpdated(plan_id=plan_id, default_parameters={}, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload["default_parameters"] == {}
    assert "default_parameters" in payload


@pytest.mark.unit
def test_from_stored_rebuilds_default_parameters_updated() -> None:
    plan_id = uuid4()
    stored = _stored(
        "PlanDefaultParametersUpdated",
        {
            "plan_id": str(plan_id),
            "default_parameters": _SAMPLE_DEFAULTS,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PlanDefaultParametersUpdated(
        plan_id=plan_id, default_parameters=_SAMPLE_DEFAULTS, occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_default_parameters_updated() -> None:
    original = PlanDefaultParametersUpdated(
        plan_id=uuid4(), default_parameters=_SAMPLE_DEFAULTS, occurred_at=_NOW
    )
    stored = _stored("PlanDefaultParametersUpdated", to_payload(original))
    assert from_stored(stored) == original


# ---------- PlanWireAdded / PlanWireRemoved ----------


@pytest.mark.unit
def test_event_type_name_returns_wire_added_class_name() -> None:
    event = PlanWireAdded(
        plan_id=uuid4(),
        source_asset_id=uuid4(),
        source_port_name="trigger_out",
        target_asset_id=uuid4(),
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PlanWireAdded"


@pytest.mark.unit
def test_event_type_name_returns_wire_removed_class_name() -> None:
    event = PlanWireRemoved(
        plan_id=uuid4(),
        source_asset_id=uuid4(),
        source_port_name="trigger_out",
        target_asset_id=uuid4(),
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PlanWireRemoved"


@pytest.mark.unit
def test_to_payload_serializes_wire_added_with_full_4_tuple() -> None:
    plan_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    event = PlanWireAdded(
        plan_id=plan_id,
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "plan_id": str(plan_id),
        "source_asset_id": str(src_id),
        "source_port_name": "trigger_out",
        "target_asset_id": str(tgt_id),
        "target_port_name": "trigger_in",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_wire_removed_with_full_4_tuple() -> None:
    """Wire removal carries all 4 components because the Wire's identity
    IS the 4-tuple (no shorter unique key)."""
    plan_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    event = PlanWireRemoved(
        plan_id=plan_id,
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "plan_id": str(plan_id),
        "source_asset_id": str(src_id),
        "source_port_name": "trigger_out",
        "target_asset_id": str(tgt_id),
        "target_port_name": "trigger_in",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_wire_added() -> None:
    plan_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    stored = _stored(
        "PlanWireAdded",
        {
            "plan_id": str(plan_id),
            "source_asset_id": str(src_id),
            "source_port_name": "trigger_out",
            "target_asset_id": str(tgt_id),
            "target_port_name": "trigger_in",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PlanWireAdded(
        plan_id=plan_id,
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_wire_removed() -> None:
    plan_id = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    stored = _stored(
        "PlanWireRemoved",
        {
            "plan_id": str(plan_id),
            "source_asset_id": str(src_id),
            "source_port_name": "trigger_out",
            "target_asset_id": str(tgt_id),
            "target_port_name": "trigger_in",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PlanWireRemoved(
        plan_id=plan_id,
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_wire_added() -> None:
    original = PlanWireAdded(
        plan_id=uuid4(),
        source_asset_id=uuid4(),
        source_port_name="trigger_out",
        target_asset_id=uuid4(),
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )
    stored = _stored("PlanWireAdded", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_wire_removed() -> None:
    original = PlanWireRemoved(
        plan_id=uuid4(),
        source_asset_id=uuid4(),
        source_port_name="trigger_out",
        target_asset_id=uuid4(),
        target_port_name="trigger_in",
        occurred_at=_NOW,
    )
    stored = _stored("PlanWireRemoved", to_payload(original))
    assert from_stored(stored) == original


# ---------- dual-key fallback: legacy snapshot payload keys ----------
#
# Per the direct-rename pattern: legacy PlanDefined payloads carried
# `method_needed_capabilities_snapshot` + `asset_capabilities_snapshot`
# keys. Current payloads carry the `*_families_snapshot` equivalents.
# from_stored reads the new key first, falls back to the legacy key.
# These tests pin the fallback so a future refactor can't silently
# break replay safety.


@pytest.mark.unit
def test_from_stored_reads_legacy_asset_capabilities_snapshot_payload_key() -> None:
    """Pre-5i payloads use `asset_capabilities_snapshot` (with
    `method_needed_capabilities_snapshot` for the method side). from_stored
    must populate the new dataclass fields from the legacy keys."""
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    asset_id = uuid4()
    legacy_cap_id = uuid4()
    stored = _stored(
        "PlanDefined",
        {
            "plan_id": str(plan_id),
            "name": "LegacyPlan",
            "practice_id": str(practice_id),
            "asset_ids": [str(asset_id)],
            "method_id": str(method_id),
            # LEGACY keys (no `*_families_snapshot` keys present)
            "method_needed_capabilities_snapshot": [str(legacy_cap_id)],
            "asset_capabilities_snapshot": {str(asset_id): [str(legacy_cap_id)]},
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, PlanDefined)
    assert rebuilt.method_needed_family_ids_snapshot == (legacy_cap_id,)
    assert rebuilt.asset_families_snapshot == {asset_id: (legacy_cap_id,)}


@pytest.mark.unit
def test_from_stored_prefers_new_families_snapshot_over_legacy_key() -> None:
    """When BOTH the new and legacy keys are present (defensive case
    against partial migration), the new key wins. This locks the
    `.get(new, .get(legacy, default))` precedence."""
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    asset_id = uuid4()
    new_id = uuid4()
    legacy_id = uuid4()
    stored = _stored(
        "PlanDefined",
        {
            "plan_id": str(plan_id),
            "name": "DualKeyPlan",
            "practice_id": str(practice_id),
            "asset_ids": [str(asset_id)],
            "method_id": str(method_id),
            # BOTH keys present; new should win
            "method_needed_family_ids_snapshot": [str(new_id)],
            "method_needed_capabilities_snapshot": [str(legacy_id)],
            "asset_families_snapshot": {str(asset_id): [str(new_id)]},
            "asset_capabilities_snapshot": {str(asset_id): [str(legacy_id)]},
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, PlanDefined)
    assert rebuilt.method_needed_family_ids_snapshot == (new_id,)
    assert rebuilt.asset_families_snapshot == {asset_id: (new_id,)}


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "PlanDefined",
        "PlanVersioned",
        "PlanDeprecated",
        "PlanDefaultParametersUpdated",
        "PlanWireAdded",
        "PlanWireRemoved",
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
