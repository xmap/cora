"""Fixture aggregate state + the SlotAssetBinding VO.

A `Fixture` records one materialization of an Assembly blueprint
into a concrete cluster of pre-existing Assets. Operators at light
sources speak of "the fixture" for the bolted-together cluster of
instruments on the bench; an Assembly is the reusable blueprint of
a Fixture and a Fixture is one realized binding of Assets to that
blueprint's slots.

The aggregate lives on its own stream type (`Fixture`), one stream
per fixture_id; each stream contains exactly one
`FixtureRegistered` event (Visit-instance pattern per the design
memo).

State is therefore append-only-genesis: the evolver folds the single
event into a `Fixture` dataclass and any subsequent event would be a
future re-registration slice (not in v1).

`slot_asset_bindings` is `frozenset[SlotAssetBinding]` where each
binding is a `(slot_name, asset_id)` pair. Multiple bindings may
share a slot_name (`OneOrMore` / `ZeroOrMore` cardinality on the
referenced TemplateSlot); each binding is identity-by-pair.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.shared.identifier import PersistentIdentifier
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class SlotAssetBinding:
    """A single slot-to-asset binding within a Fixture.

    The 2-tuple `(slot_name, asset_id)` IS the identity; a frozenset
    deduplicates on the tuple. The same `slot_name` may appear in
    multiple bindings when the referenced TemplateSlot's cardinality
    is OneOrMore or ZeroOrMore.
    """

    slot_name: str
    asset_id: UUID


@dataclass(frozen=True)
class Fixture:
    """Aggregate root: one materialization of an Assembly blueprint.

    `id` is the opaque fixture_id (UUID stream key).
    `assembly_id` references the Assembly being instantiated.
    `assembly_content_hash` captures the Assembly's content_hash AT
    REGISTRATION TIME (snapshot, not a back-reference) so the
    Fixture stays interpretable if the Assembly is later versioned
    or deprecated.
    `surface_id` scopes the Fixture to a Trust BC Surface for authz
    queries.
    `slot_asset_bindings` is the full slot binding set captured at
    registration.
    `parameter_overrides` is the operator-supplied dict validated
    against the Assembly's parameter_overrides_schema.
    """

    id: UUID
    assembly_id: UUID
    assembly_content_hash: str
    surface_id: UUID
    slot_asset_bindings: frozenset[SlotAssetBinding] = field(
        default_factory=frozenset[SlotAssetBinding]
    )
    parameter_overrides: dict[str, Any] = field(default_factory=dict[str, Any])
    registered_at: datetime | None = None
    # Fold-symmetry attribution paired with `registered_at` per
    # [[project-fold-symmetry-design]]. `registered_by` is folded from
    # `FixtureRegistered.registered_by` (the principal that issued the
    # register_fixture command). Default-None so legacy streams fold
    # cleanly via the additive-state pattern.
    registered_by: ActorId | None = None
    # PIDINST v1.0 Property 1 persistent identifier (DOI or Handle).
    # Data-substrate field landed ahead of the write path (mirrors slice
    # E.1's Asset.commissioned_at pattern). Reads None at end-of-fold
    # until the future assign_fixture_persistent_id slice ships the
    # FixturePersistentIdAssigned event + evolver fold that flips this
    # from None to Some. Set-once at the aggregate level per F3.3
    # Findable immutability. The PersistentIdentifier VO is reused
    # unchanged from the Asset aggregate per Lock 2.
    persistent_id: PersistentIdentifier | None = None


class FixtureAlreadyExistsError(Exception):
    """Attempted to register a Fixture against a stream that already exists.

    Defensive guard; with UUIDv7 fixture_ids this is essentially
    impossible but the decider checks state-must-be-None as a sanity
    invariant.
    """

    def __init__(self, fixture_id: UUID) -> None:
        super().__init__(f"Fixture {fixture_id} already exists")
        self.fixture_id = fixture_id


class FixtureNotFoundError(Exception):
    """No Fixture exists for the given fixture_id.

    Handler-side projection check; fired by `attach_asset_to_fixture`
    (and future `detach_asset_from_fixture`, get_fixture, list_fixtures)
    when the target Fixture stream has no `FixtureRegistered` event.
    Maps to 404 at the REST + MCP boundary.
    """

    def __init__(self, fixture_id: UUID) -> None:
        super().__init__(f"Fixture {fixture_id} not found")
        self.fixture_id = fixture_id


class FixturePersistentIdAlreadyAssignedError(Exception):
    """Attempted to assign a persistent_id to a Fixture that already carries one.

    Set-once at the aggregate level per PIDINST v1.0 F3.3 Findable
    immutability: once `Fixture.persistent_id` is set, no further
    FixturePersistentIdAssigned event can land. Both the same-value and
    different-value retry shapes collapse here; the diagnostic fields
    carry the current and attempted PersistentIdentifier so operators
    see which assign collided. Mirrors
    `AssetPersistentIdAlreadyAssignedError` on the sibling Asset
    aggregate.
    """

    def __init__(
        self,
        fixture_id: UUID,
        *,
        current: "PersistentIdentifier",
        attempted: "PersistentIdentifier",
    ) -> None:
        super().__init__(
            f"Fixture {fixture_id} already has persistent identifier "
            f"{current.scheme.value}={current.value!r}; "
            f"attempted to assign {attempted.scheme.value}={attempted.value!r}; "
            "persistent_id is set-once"
        )
        self.fixture_id = fixture_id
        self.current = current
        self.attempted = attempted


class MalformedFixturePersistentIdentifierError(Exception):
    """A stored FixturePersistentIdAssigned payload failed deserialization.

    Wraps any underlying `ValueError` raised by
    `PersistentIdentifierScheme(...)` or `PersistentIdentifier(...)` at
    `from_stored` time, per the [[project-from-stored-wrap-convention]]
    precedent (mirrors `MalformedPersistentIdentifierError` on the
    sibling Asset aggregate). The evolver itself never raises; it
    trusts that `from_stored` already wrapped any malformed payload as
    this error class.
    """


__all__ = [
    "Fixture",
    "FixtureAlreadyExistsError",
    "FixtureNotFoundError",
    "FixturePersistentIdAlreadyAssignedError",
    "MalformedFixturePersistentIdentifierError",
    "PersistentIdentifier",
    "SlotAssetBinding",
]
