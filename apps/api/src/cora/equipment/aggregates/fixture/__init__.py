"""Fixture aggregate: one materialization of an Assembly blueprint.

Lives on its own stream type (`Fixture`), one stream per fixture_id,
exactly one `FixtureRegistered` event per stream (Visit-instance
pattern). The referenced Assets are NOT created atomically with the
FixtureRegistered event; they pre-exist (registered via the
standard `register_asset` slice) and the registration event simply
records the mapping.

See `project_assembly_aggregate_design` for the locked design memo.
"""

from cora.equipment.aggregates.fixture.events import (
    FixtureEvent,
    FixturePersistentIdAssigned,
    FixtureRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.fixture.evolver import evolve, fold
from cora.equipment.aggregates.fixture.read import load_fixture
from cora.equipment.aggregates.fixture.state import (
    Fixture,
    FixtureAlreadyExistsError,
    FixtureNotFoundError,
    FixturePersistentIdAlreadyAssignedError,
    MalformedFixturePersistentIdentifierError,
    PersistentIdentifier,
    SlotAssetBinding,
)

__all__ = [
    "Fixture",
    "FixtureAlreadyExistsError",
    "FixtureEvent",
    "FixtureNotFoundError",
    "FixturePersistentIdAlreadyAssignedError",
    "FixturePersistentIdAssigned",
    "FixtureRegistered",
    "MalformedFixturePersistentIdentifierError",
    "PersistentIdentifier",
    "SlotAssetBinding",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_fixture",
    "to_payload",
]
