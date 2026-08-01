"""Unit tests for the Recipe aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.recipe import (
    BindingRef,
    RecipeDefined,
    RecipeDeprecated,
    RecipeSetpointStep,
    RecipeVersioned,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _steps() -> tuple[RecipeSetpointStep, ...]:
    return (RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),)


def _make_defined(rid: object, cid: object) -> RecipeDefined:
    return RecipeDefined(
        recipe_id=rid,  # type: ignore[arg-type]
        name="R",
        capability_id=cid,  # type: ignore[arg-type]
        steps=_steps(),
        occurred_at=_NOW,
    )


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Recipe",
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
def test_event_type_name_returns_class_name_for_each_arm() -> None:
    rid, cid = uuid4(), uuid4()
    defn = _make_defined(rid, cid)
    ver = RecipeVersioned(recipe_id=rid, version_tag="v1", steps=_steps(), occurred_at=_NOW)
    dep = RecipeDeprecated(reason="Superseded", recipe_id=rid, occurred_at=_NOW)
    assert event_type_name(defn) == "RecipeDefined"
    assert event_type_name(ver) == "RecipeVersioned"
    assert event_type_name(dep) == "RecipeDeprecated"


@pytest.mark.unit
def test_to_payload_recipe_defined_serializes_full_payload() -> None:
    rid, cid = uuid4(), uuid4()
    defn = _make_defined(rid, cid)
    payload = to_payload(defn)
    assert payload["recipe_id"] == str(rid)
    assert payload["capability_id"] == str(cid)
    assert payload["name"] == "R"
    assert payload["occurred_at"] == _NOW.isoformat()
    assert "steps" in payload


@pytest.mark.unit
def test_to_payload_recipe_versioned_serializes_version_tag_and_steps() -> None:
    rid = uuid4()
    ver = RecipeVersioned(recipe_id=rid, version_tag="v2", steps=_steps(), occurred_at=_NOW)
    payload = to_payload(ver)
    assert payload["version_tag"] == "v2"
    assert "steps" in payload
    assert "name" not in payload  # name preserved on state, not in payload
    assert "capability_id" not in payload  # capability_id preserved on state, not in payload


@pytest.mark.unit
def test_to_payload_recipe_deprecated_serializes_replaced_by_or_none() -> None:
    rid, succ = uuid4(), uuid4()
    dep_none = RecipeDeprecated(reason="Superseded", recipe_id=rid, occurred_at=_NOW)
    dep_with = RecipeDeprecated(
        reason="Superseded", recipe_id=rid, replaced_by_recipe_id=succ, occurred_at=_NOW
    )
    assert to_payload(dep_none)["replaced_by_recipe_id"] is None
    assert to_payload(dep_with)["replaced_by_recipe_id"] == str(succ)


@pytest.mark.unit
def test_from_stored_round_trips_recipe_defined() -> None:
    rid, cid = uuid4(), uuid4()
    original = _make_defined(rid, cid)
    stored = _stored("RecipeDefined", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_round_trips_recipe_versioned() -> None:
    rid = uuid4()
    original = RecipeVersioned(recipe_id=rid, version_tag="v3", steps=_steps(), occurred_at=_NOW)
    stored = _stored("RecipeVersioned", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_round_trips_recipe_deprecated_with_replacement() -> None:
    rid, succ = uuid4(), uuid4()
    original = RecipeDeprecated(
        reason="Superseded", recipe_id=rid, replaced_by_recipe_id=succ, occurred_at=_NOW
    )
    stored = _stored("RecipeDeprecated", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_round_trips_recipe_deprecated_without_replacement() -> None:
    rid = uuid4()
    original = RecipeDeprecated(reason="Superseded", recipe_id=rid, occurred_at=_NOW)
    stored = _stored("RecipeDeprecated", to_payload(original))
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_rejects_unknown_event_type() -> None:
    stored = _stored("RecipeFooBar", {})
    with pytest.raises(ValueError, match="Unknown RecipeEvent"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_wraps_malformed_recipe_defined_payload() -> None:
    """Missing keys / wrong types route through `deserialize_or_raise`."""
    stored = _stored("RecipeDefined", {})  # missing every required key
    with pytest.raises(ValueError, match="Malformed RecipeDefined payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_wraps_malformed_recipe_versioned_payload() -> None:
    stored = _stored("RecipeVersioned", {"recipe_id": str(uuid4())})  # missing version_tag, steps
    with pytest.raises(ValueError, match="Malformed RecipeVersioned payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_wraps_malformed_recipe_deprecated_payload() -> None:
    stored = _stored("RecipeDeprecated", {})  # missing recipe_id + occurred_at
    with pytest.raises(ValueError, match="Malformed RecipeDeprecated payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_wraps_recipe_defined_with_bad_uuid_payload() -> None:
    stored = _stored(
        "RecipeDefined",
        {
            "recipe_id": "not-a-uuid",
            "name": "R",
            "capability_id": str(uuid4()),
            "steps": {"steps": []},
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed RecipeDefined payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_wraps_recipe_defined_with_unknown_step_kind() -> None:
    stored = _stored(
        "RecipeDefined",
        {
            "recipe_id": str(uuid4()),
            "name": "R",
            "capability_id": str(uuid4()),
            "steps": {"steps": [{"kind": "unknown_kind"}]},
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed RecipeDefined payload"):
        from_stored(stored)


@pytest.mark.unit
def test_from_stored_wraps_recipe_versioned_with_unknown_step_kind() -> None:
    stored = _stored(
        "RecipeVersioned",
        {
            "recipe_id": str(uuid4()),
            "version_tag": "v1",
            "steps": {"steps": [{"kind": "unknown_kind"}]},
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed RecipeVersioned payload"):
        from_stored(stored)
