"""Evolver: replay events to reconstruct Fixture state.

Genesis is single-event per Visit-instance pattern: one stream per
fixture_id, exactly one `FixtureRegistered` event per stream. The
stream stays append-only-monotonic: events are FixtureRegistered
exactly once, then optionally one FixturePersistentIdAssigned.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.equipment.aggregates.asset import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.equipment.aggregates.fixture.events import (
    FixtureEvent,
    FixturePersistentIdAssigned,
    FixtureRegistered,
)
from cora.equipment.aggregates.fixture.state import (
    Fixture,
    FixtureAlreadyExistsError,
    FixtureNotFoundError,
)


def evolve(
    state: Fixture | None,
    event: FixtureEvent,
) -> Fixture:
    """Apply one event to the current state.

    Genesis: `FixtureRegistered` lands exactly once per stream and a
    duplicate raises rather than silently overwriting prior state.
    Post-genesis: `FixturePersistentIdAssigned` folds set-once into
    `state.persistent_id`; the decider guards strict-not-idempotent
    semantics at command time, so the evolver trusts the input.
    """
    match event:
        case FixtureRegistered(
            fixture_id=fixture_id,
            assembly_id=assembly_id,
            assembly_content_hash=assembly_content_hash,
            surface_id=surface_id,
            slot_asset_bindings=slot_asset_bindings,
            parameter_overrides=parameter_overrides,
            occurred_at=occurred_at,
        ):
            if state is not None:
                raise FixtureAlreadyExistsError(state.id)
            return Fixture(
                id=fixture_id,
                assembly_id=assembly_id,
                assembly_content_hash=assembly_content_hash,
                surface_id=surface_id,
                slot_asset_bindings=slot_asset_bindings,
                parameter_overrides=parameter_overrides,
                registered_at=occurred_at,
            )
        case FixturePersistentIdAssigned(
            fixture_id=fixture_id,
            persistent_id_scheme=scheme,
            persistent_id_value=value,
        ):
            if state is None:
                raise FixtureNotFoundError(fixture_id)
            return replace(
                state,
                persistent_id=PersistentIdentifier(
                    scheme=PersistentIdentifierScheme(scheme),
                    value=value,
                ),
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[FixtureEvent]) -> Fixture | None:
    """Replay a stream of events from the empty initial state."""
    state: Fixture | None = None
    for event in events:
        state = evolve(state, event)
    return state
