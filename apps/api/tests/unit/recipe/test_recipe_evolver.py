"""Unit tests for the Recipe aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.recipe import (
    BindingRef,
    RecipeDefined,
    RecipeDeprecated,
    RecipeSetpointStep,
    RecipeStatus,
    RecipeVersioned,
    evolve,
    fold,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _defined(**overrides: object) -> RecipeDefined:
    base: dict[str, object] = dict(
        recipe_id=uuid4(),
        name="R",
        capability_id=uuid4(),
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        occurred_at=_NOW,
    )
    base.update(overrides)
    return RecipeDefined(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_recipe_defined_folds_into_defined_status() -> None:
    state = evolve(None, _defined())
    assert state.status == RecipeStatus.DEFINED
    assert state.version is None
    assert state.replaced_by_recipe_id is None


@pytest.mark.unit
def test_recipe_defined_folds_name_capability_id_and_steps() -> None:
    rid, cid = uuid4(), uuid4()
    event = _defined(
        recipe_id=rid,
        name="tomography",
        capability_id=cid,
        steps=(RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),),
    )
    state = evolve(None, event)
    assert state.id == rid
    assert state.name.value == "tomography"
    assert state.capability_id == cid
    assert len(state.steps) == 1


@pytest.mark.unit
def test_recipe_versioned_replaces_steps_wholesale_and_preserves_identity() -> None:
    rid, cid = uuid4(), uuid4()
    state = evolve(
        None,
        _defined(
            recipe_id=rid,
            capability_id=cid,
            steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        ),
    )
    new_steps = (
        RecipeSetpointStep(address="dev:x", value=2.0),
        RecipeSetpointStep(address="dev:y", value=3.0),
    )
    state2 = evolve(
        state,
        RecipeVersioned(recipe_id=rid, version_tag="v1", steps=new_steps, occurred_at=_NOW),
    )
    assert state2.status == RecipeStatus.VERSIONED
    assert state2.version == "v1"
    assert state2.steps == new_steps
    assert state2.id == rid  # identity preserved
    assert state2.capability_id == cid  # capability_id IMMUTABLE per Pattern P
    assert state2.name == state.name


@pytest.mark.unit
def test_recipe_deprecated_preserves_steps_and_capability_id_for_audit() -> None:
    rid, cid, succ = uuid4(), uuid4(), uuid4()
    state = evolve(None, _defined(recipe_id=rid, capability_id=cid))
    state2 = evolve(
        state,
        RecipeDeprecated(
            reason="Superseded", recipe_id=rid, replaced_by_recipe_id=succ, occurred_at=_NOW
        ),
    )
    assert state2.status == RecipeStatus.DEPRECATED
    assert state2.replaced_by_recipe_id == succ
    assert state2.steps == state.steps  # PRESERVED
    assert state2.capability_id == cid  # PRESERVED


@pytest.mark.unit
def test_recipe_deprecated_without_replacement_carries_none_pointer() -> None:
    rid = uuid4()
    state = evolve(None, _defined(recipe_id=rid))
    state2 = evolve(state, RecipeDeprecated(reason="Superseded", recipe_id=rid, occurred_at=_NOW))
    assert state2.status == RecipeStatus.DEPRECATED
    assert state2.replaced_by_recipe_id is None


@pytest.mark.unit
def test_recipe_versioned_preserves_replaced_by_pointer_if_set() -> None:
    """Defensive: a Versioned event after Deprecated would never happen in well-formed
    streams; the evolver still preserves any prior replaced_by_recipe_id."""
    rid, succ = uuid4(), uuid4()
    state = evolve(None, _defined(recipe_id=rid))
    state = evolve(
        state,
        RecipeDeprecated(
            reason="Superseded", recipe_id=rid, replaced_by_recipe_id=succ, occurred_at=_NOW
        ),
    )
    state2 = evolve(
        state,
        RecipeVersioned(
            recipe_id=rid,
            version_tag="vX",
            steps=(RecipeSetpointStep(address="dev:x", value=9.0),),
            occurred_at=_NOW,
        ),
    )
    assert state2.replaced_by_recipe_id == succ


@pytest.mark.unit
def test_evolve_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError):
        evolve(
            None,
            RecipeVersioned(
                recipe_id=uuid4(),
                version_tag="v1",
                steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolve_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError):
        evolve(None, RecipeDeprecated(reason="Superseded", recipe_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_replays_defined_only_stream() -> None:
    state = fold([_defined()])
    assert state is not None
    assert state.status == RecipeStatus.DEFINED


@pytest.mark.unit
def test_fold_replays_defined_versioned_deprecated_chain() -> None:
    rid = uuid4()
    events = [
        _defined(recipe_id=rid),
        RecipeVersioned(
            recipe_id=rid,
            version_tag="v1",
            steps=(RecipeSetpointStep(address="dev:x", value=2.0),),
            occurred_at=_NOW,
        ),
        RecipeDeprecated(reason="Superseded", recipe_id=rid, occurred_at=_NOW),
    ]
    state = fold(events)
    assert state is not None
    assert state.status == RecipeStatus.DEPRECATED
    assert state.version == "v1"  # last-emitted version_tag preserved across deprecation


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None
