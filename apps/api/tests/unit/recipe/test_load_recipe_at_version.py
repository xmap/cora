"""Unit tests for `load_recipe_at_version`.

Per [[project-run-procedure-replay-design]] §Cross-BC seam additions
+ §Locks. The helper resolves a Recipe to the snapshot pinned by an
earlier `RecipeExpansionRecorded.recipe_version` via first-match-from-head
semantics over the Recipe event stream.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.recipe.aggregates.recipe import (
    RecipeDefined,
    RecipeDeprecated,
    RecipeSetpointStep,
    RecipeStatus,
    RecipeVersioned,
    RecipeVersionNotFoundError,
    event_type_name,
    load_recipe_at_version,
    to_payload,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_event(
    store: InMemoryEventStore,
    recipe_id: UUID,
    expected_version: int,
    event: object,
) -> None:
    await store.append(
        stream_type="Recipe",
        stream_id=recipe_id,
        expected_version=expected_version,
        events=[
            to_new_event(
                event_type=event_type_name(event),  # type: ignore[arg-type]
                payload=to_payload(event),  # type: ignore[arg-type]
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            ),
        ],
    )


def _defined(recipe_id: UUID, capability_id: UUID) -> RecipeDefined:
    return RecipeDefined(
        recipe_id=recipe_id,
        name="R",
        capability_id=capability_id,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        occurred_at=_NOW,
    )


def _versioned(recipe_id: UUID, tag: str, value: float) -> RecipeVersioned:
    return RecipeVersioned(
        recipe_id=recipe_id,
        version_tag=tag,
        steps=(RecipeSetpointStep(address="dev:x", value=value),),
        occurred_at=_NOW,
    )


@pytest.mark.unit
async def test_load_recipe_at_version_with_none_tag_returns_post_genesis_state() -> None:
    store = InMemoryEventStore()
    recipe_id = uuid4()
    cap_id = uuid4()
    await _seed_event(store, recipe_id, 0, _defined(recipe_id, cap_id))

    state = await load_recipe_at_version(store, recipe_id, None)

    assert state is not None
    assert state.id == recipe_id
    assert state.status == RecipeStatus.DEFINED
    assert state.version is None


@pytest.mark.unit
async def test_load_recipe_at_version_with_matching_tag_returns_post_version_fold() -> None:
    store = InMemoryEventStore()
    recipe_id = uuid4()
    cap_id = uuid4()
    await _seed_event(store, recipe_id, 0, _defined(recipe_id, cap_id))
    await _seed_event(store, recipe_id, 1, _versioned(recipe_id, "v1", 2.0))

    state = await load_recipe_at_version(store, recipe_id, "v1")

    assert state is not None
    assert state.version == "v1"
    assert state.status == RecipeStatus.VERSIONED
    assert state.steps[0].value == 2.0  # type: ignore[union-attr]


@pytest.mark.unit
async def test_load_recipe_at_version_with_two_matches_returns_first_match() -> None:
    """version_recipe allows tag re-use (no UNIQUE constraint per the
    Recipe BC state docstring); first-match-from-head is the deterministic
    choice because the second match could not have existed when the earlier
    RecipeExpansionRecorded was written."""
    store = InMemoryEventStore()
    recipe_id = uuid4()
    cap_id = uuid4()
    await _seed_event(store, recipe_id, 0, _defined(recipe_id, cap_id))
    await _seed_event(store, recipe_id, 1, _versioned(recipe_id, "v1", 2.0))
    await _seed_event(store, recipe_id, 2, _versioned(recipe_id, "v2", 3.0))
    await _seed_event(store, recipe_id, 3, _versioned(recipe_id, "v1", 4.0))

    state = await load_recipe_at_version(store, recipe_id, "v1")

    assert state is not None
    assert state.steps[0].value == 2.0  # type: ignore[union-attr]  # first v1 wins


@pytest.mark.unit
async def test_load_recipe_at_version_with_no_matching_tag_raises_not_found() -> None:
    store = InMemoryEventStore()
    recipe_id = uuid4()
    cap_id = uuid4()
    await _seed_event(store, recipe_id, 0, _defined(recipe_id, cap_id))
    await _seed_event(store, recipe_id, 1, _versioned(recipe_id, "v1", 2.0))

    with pytest.raises(RecipeVersionNotFoundError) as exc:
        await load_recipe_at_version(store, recipe_id, "vX")

    assert exc.value.recipe_id == recipe_id
    assert exc.value.version_tag == "vX"


@pytest.mark.unit
async def test_load_recipe_at_version_with_empty_stream_returns_none() -> None:
    store = InMemoryEventStore()
    recipe_id = uuid4()

    state = await load_recipe_at_version(store, recipe_id, None)

    assert state is None


@pytest.mark.unit
async def test_load_recipe_at_version_folds_deprecated_event_before_matching_version() -> None:
    """Defensive: the helper does not assume FSM cleanliness; if a
    `RecipeDeprecated` event appears before the matching `RecipeVersioned`
    (the FSM forbids it today, but the helper folds whatever the stream
    carries), the fold runs through and the matching version is still
    located."""
    store = InMemoryEventStore()
    recipe_id = uuid4()
    cap_id = uuid4()
    await _seed_event(store, recipe_id, 0, _defined(recipe_id, cap_id))
    await _seed_event(
        store,
        recipe_id,
        1,
        RecipeDeprecated(
            reason="Superseded",
            recipe_id=recipe_id,
            replaced_by_recipe_id=None,
            occurred_at=_NOW,
        ),
    )
    await _seed_event(store, recipe_id, 2, _versioned(recipe_id, "v1", 2.0))

    state = await load_recipe_at_version(store, recipe_id, "v1")

    assert state is not None
    assert state.version == "v1"
