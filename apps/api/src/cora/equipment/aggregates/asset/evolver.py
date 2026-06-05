"""Evolver: replay events to reconstruct Asset state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `AssetEvent` without a matching match arm here.

Lifecycle mapping per event type:
  - `AssetRegistered`              -> COMMISSIONED  (genesis)
  - `AssetActivated`               -> ACTIVE
  - `AssetDecommissioned`          -> DECOMMISSIONED  (3-source guard at decider)
  - `AssetRelocated`               -> (lifecycle UNCHANGED; mutates parent_id only)
  - `AssetMaintenanceEntered`      -> MAINTENANCE
  - `AssetMaintenanceExited`       -> ACTIVE
  - `AssetFamilyAdded`         -> (lifecycle UNCHANGED; inserts into family_ids frozenset)
  - `AssetFamilyRemoved`       -> (lifecycle UNCHANGED; removes from family_ids frozenset)
  - `AssetDegraded`                -> (lifecycle UNCHANGED; condition -> DEGRADED)
  - `AssetFaulted`                 -> (lifecycle UNCHANGED; condition -> FAULTED)
  - `AssetRestored`                -> (lifecycle UNCHANGED; condition -> NOMINAL)
  - `AssetSettingsUpdated`         -> (lifecycle UNCHANGED; settings -> event.settings)
  - `AssetPortAdded`               -> (lifecycle UNCHANGED; inserts AssetPort into ports frozenset)
  - `AssetPortRemoved`             -> (lifecycle UNCHANGED; removes AssetPort matching name)
  - `AssetAlternateIdentifierAdded`   -> (lifecycle UNCHANGED; inserts into
    alternate_identifiers frozenset)
  - `AssetAlternateIdentifierRemoved` -> (lifecycle UNCHANGED; removes from
    alternate_identifiers frozenset)
  - `AssetOwnerAdded`              -> (lifecycle UNCHANGED; inserts AssetOwner
    into owners frozenset)
  - `AssetOwnerRemoved`            -> (lifecycle UNCHANGED; removes owner
    matching name from owners frozenset)

The lifecycle mapping is hardcoded per match arm — the event type
IS the lifecycle-change indicator (no lifecycle field in event
payloads). Same precedent as Subject / Family. Condition
mapping follows the same pattern (event type encodes the target
condition; no condition field in payload).

`level` IS reconstructed from the payload of AssetRegistered (set
at registration, never changes; payload-carried by design — see
events.py docstring). `parent_id` IS reconstructed from
AssetRegistered's payload AND mutated by AssetRelocated's
`to_parent_id` field. `family_ids` defaults to empty frozenset on
AssetRegistered (additive-state pattern; existing AssetRegistered
events without the family_ids field fold cleanly without an upcaster) and is
mutated incrementally by `AssetFamilyAdded` /
`AssetFamilyRemoved`.

**Critical invariant**: every transition arm MUST carry
`family_ids` AND `condition` AND `settings` AND `ports` AND
`drawing` AND `model_id` AND `alternate_identifiers` AND `owners`
AND `fixture_id` AND `commissioned_at` AND `decommissioned_at`
through from prior state. Constructing
`Asset(id=..., name=..., level=..., parent_id=..., lifecycle=...)`
without explicitly passing them would silently WIPE the fields to
their defaults (empty frozenset / NOMINAL / empty dict / empty
frozenset / None / None / empty frozenset / empty frozenset /
None). `family_ids` was added with a default solely for
additive-state forward compatibility on genesis events;
`condition`, `settings`, `ports`, `drawing`, `model_id`,
`alternate_identifiers`, `owners`, and `fixture_id` followed the
same additive pattern. Transition arms must explicitly carry all
nine. `model_id` is set ONCE at registration per the
model-binding design memo (Lock A) and never changes post-genesis,
but transition arms still must carry it forward like any other
Asset field. `fixture_id` toggles None <-> Some(fixture_id) via
AssetAttachedToFixture / AssetDetachedFromFixture; every other
transition arm preserves it. Pinned by
`test_evolve_<transition>_preserves_capabilities`,
`test_evolve_<transition>_preserves_condition`,
`test_evolve_<transition>_preserves_settings`,
`test_evolve_<transition>_preserves_ports`,
`test_evolve_<transition>_preserves_drawing`,
`test_evolve_<transition>_preserves_model_id`,
`test_evolve_<transition>_preserves_alternate_identifiers`,
`test_evolve_<transition>_preserves_owners`, and
`test_evolve_<transition>_preserves_fixture_id` for each transition.

Transition events applied to empty state raise ValueError: they
can never appear before `AssetRegistered` in a well-formed stream.
The `require_state` helper keeps the per-arm bodies short
(precedent locked by Subject's evolver).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierRemoved,
    AssetAttachedToFixture,
    AssetDecommissioned,
    AssetDegraded,
    AssetDetachedFromFixture,
    AssetEvent,
    AssetFamilyAdded,
    AssetFamilyRemoved,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetMaintenanceExited,
    AssetOwnerAdded,
    AssetOwnerRemoved,
    AssetPersistentIdAssigned,
    AssetPortAdded,
    AssetPortRemoved,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetSettingsUpdated,
)
from cora.equipment.aggregates.asset.state import (
    Asset,
    AssetCondition,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetPort,
    PersistentIdentifier,
    PersistentIdentifierScheme,
    PortDirection,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Asset | None, event: AssetEvent) -> Asset:
    """Apply one event to the current state."""
    match event:
        case AssetRegistered(
            asset_id=asset_id,
            name=name,
            level=level,
            parent_id=parent_id,
            occurred_at=occurred_at,
            drawing=drawing,
            model_id=model_id,
            alternate_identifiers=alternate_identifiers,
            owners=owners,
        ):
            _ = state  # AssetRegistered is the genesis event; prior state ignored
            return Asset(
                id=asset_id,
                name=AssetName(name),
                level=AssetLevel(level),
                parent_id=parent_id,
                lifecycle=AssetLifecycle.COMMISSIONED,
                drawing=drawing,
                model_id=model_id,
                alternate_identifiers=alternate_identifiers,
                owners=owners,
                fixture_id=None,
                # Asset enters Commissioned at genesis; AssetRegistered
                # IS the commissioning event per L2 of the persistent-id
                # design memo. Folding occurred_at avoids a new
                # AssetCommissioned event for what the existing event
                # already encodes.
                commissioned_at=occurred_at,
                # family_ids defaults to empty frozenset; condition
                # defaults to NOMINAL. Additive-state pattern:
                # default-via-state so legacy streams without these
                # fields fold cleanly without an upcaster.
                # alternate_identifiers / owners defaults are empty
                # frozenset on the event side (additive-payload
                # pattern), so legacy streams missing those keys fold
                # to the empty frozenset without an upcaster.
                # fixture_id is set later by AssetAttachedToFixture
                # `attach_asset_to_fixture`; register_asset never sets it inline.
            )
        case AssetActivated():
            prior = require_state(state, "AssetActivated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.ACTIVE,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetDecommissioned(occurred_at=occurred_at):
            prior = require_state(state, "AssetDecommissioned")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.DECOMMISSIONED,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=occurred_at,
                persistent_id=prior.persistent_id,
            )
        case AssetRelocated(to_parent_id=to_parent_id):
            # Hierarchy mutation: only parent_id changes; lifecycle / level
            # / name / family_ids / condition / settings carry over from
            # prior state. The from_parent_id and reason fields in the
            # event aren't read here (audit metadata; prior state's
            # parent_id is the source of truth for the read path).
            prior = require_state(state, "AssetRelocated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=to_parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetMaintenanceEntered():
            prior = require_state(state, "AssetMaintenanceEntered")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.MAINTENANCE,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetMaintenanceExited():
            prior = require_state(state, "AssetMaintenanceExited")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.ACTIVE,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetFamilyAdded(family_id=family_id):
            # Family mutation: only `family_ids` changes; everything
            # else carries over. Frozenset semantics: adding an already-
            # present id is a no-op AT THE EVOLVER LAYER (the decider's
            # strict-not-idempotent guard enforces "must not already be
            # present" at command time).
            prior = require_state(state, "AssetFamilyAdded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids | {family_id},
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetFamilyRemoved(family_id=family_id):
            # Mirror of AssetFamilyAdded. Frozenset difference is a
            # no-op when the id isn't present (decider enforces
            # presence at command time). Settings are NOT auto-purged
            # when a Family is removed (5g-c lock: preserve orphans;
            # the update_asset_settings slice's null-write is the
            # cleanup path).
            prior = require_state(state, "AssetFamilyRemoved")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids - {family_id},
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetDegraded():
            # Condition mutation: only `condition` changes; everything
            # else carries over. The reason field in the event is audit
            # metadata, not folded into state. Decider's no-op-on-unchanged
            # guard prevents redundant transitions; if one slips through
            # (concurrent writers), this arm idempotently sets DEGRADED.
            prior = require_state(state, "AssetDegraded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.DEGRADED,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetFaulted():
            prior = require_state(state, "AssetFaulted")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.FAULTED,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetRestored():
            prior = require_state(state, "AssetRestored")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.NOMINAL,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetSettingsUpdated(settings=settings):
            # Settings mutation: only `settings` changes. Event payload
            # carries the FULL post-merge dict, so this arm
            # simply replaces. Validation already happened at the handler
            # boundary before append; an event in the stream is by
            # definition validated. Shallow-copy the payload dict into
            # state so mutating either side (state or event payload)
            # can't alias the other (B1 defence).
            prior = require_state(state, "AssetSettingsUpdated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=dict(settings),
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetPortAdded(
            port_name=port_name,
            direction=direction,
            signal_type=signal_type,
        ):
            # Ports mutation: only `ports` changes; everything else
            # carries over. Frozenset semantics: adding the exact
            # AssetPort tuple twice is a no-op AT THE EVOLVER LAYER;
            # the decider's strict-not-idempotent guard enforces "no
            # port with this name already exists" at command time
            # (which is stricter than tuple equality).
            prior = require_state(state, "AssetPortAdded")
            new_port = AssetPort(
                name=port_name,
                direction=PortDirection(direction),
                signal_type=signal_type,
            )
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports | {new_port},
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetPortRemoved(port_name=port_name):
            # Mirror of AssetPortAdded. Removes the port whose `name`
            # matches; AssetPort tuple equality alone wouldn't suffice
            # because we may not know the direction/signal_type at the
            # call site. Use a comprehension to filter by name. The
            # decider enforces "port with this name MUST exist" at
            # command time; the evolver-level filter is forgiving (no
            # error if name not found, since by-design the only
            # producer is the decider that already validated).
            prior = require_state(state, "AssetPortRemoved")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=frozenset(p for p in prior.ports if p.name != port_name),
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetAlternateIdentifierAdded(alternate_identifier=identifier):
            # Alternate-identifier mutation: only
            # `alternate_identifiers` changes; everything else carries
            # over. Frozenset union semantics: adding an already-
            # present (kind, value) is a no-op AT THE EVOLVER LAYER
            # (the decider's strict-not-idempotent guard enforces
            # "must not already be present" at command time per
            # [[project-asset-alternate-identifiers-design]] Lock E).
            prior = require_state(state, "AssetAlternateIdentifierAdded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers | {identifier},
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetAlternateIdentifierRemoved(alternate_identifier=identifier):
            # Mirror of AssetAlternateIdentifierAdded. Frozenset
            # difference is a no-op when the identifier isn't present;
            # the decider enforces presence at command time.
            prior = require_state(state, "AssetAlternateIdentifierRemoved")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers - {identifier},
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetOwnerAdded(owner=owner):
            # Owner mutation: only `owners` changes; everything else
            # carries over. Frozenset union semantics: adding an owner
            # already present (by full VO equality) is a no-op AT THE
            # EVOLVER LAYER; the decider's strict-not-idempotent guard
            # enforces "no owner with this name already exists" at
            # command time (which is stricter than full VO equality).
            prior = require_state(state, "AssetOwnerAdded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners | {owner},
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetPersistentIdAssigned(
            persistent_id_scheme=scheme,
            persistent_id_value=value,
        ):
            # Persistent-id mutation: only `persistent_id` changes;
            # everything else carries over. Set-once at the aggregate
            # level: the decider's
            # AssetPersistentIdAlreadyAssignedError rejects any second
            # assign at command time, so the evolver can trust that
            # prior.persistent_id is None whenever this arm fires. The
            # arm is forgiving if it ever sees a second assign at
            # replay time (would overwrite, but by-design the only
            # producer is the decider that already validated).
            prior = require_state(state, "AssetPersistentIdAssigned")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=PersistentIdentifier(
                    scheme=PersistentIdentifierScheme(scheme),
                    value=value,
                ),
            )
        case AssetOwnerRemoved(owner_name=owner_name):
            # Mirror of AssetOwnerAdded. Removes the owner whose `name`
            # matches; full-VO equality alone wouldn't suffice because
            # the remove command only carries the name. Filter via
            # comprehension. The decider enforces "owner with this
            # name MUST exist" at command time; this arm is forgiving
            # if the name isn't present (by-design the only producer
            # is the decider that already validated).
            prior = require_state(state, "AssetOwnerRemoved")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=frozenset(o for o in prior.owners if o.name != owner_name),
                fixture_id=prior.fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetAttachedToFixture(fixture_id=fixture_id):
            # Sets the back-reference. The Fixture side carries the
            # slot_name; this evolver only mutates the Asset's
            # fixture_id field. Decider rejects double-attach so this
            # always transitions None -> Some(fixture_id).
            prior = require_state(state, "AssetAttachedToFixture")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=fixture_id,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case AssetDetachedFromFixture():
            # Clears the back-reference. The Fixture's own
            # slot_asset_bindings stays unchanged (single-event-stream
            # invariant); the conformance projection notices the gap.
            # Decider rejects detach when fixture_id is None so this
            # always transitions Some(fixture_id) -> None.
            prior = require_state(state, "AssetDetachedFromFixture")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                family_ids=prior.family_ids,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
                model_id=prior.model_id,
                alternate_identifiers=prior.alternate_identifiers,
                owners=prior.owners,
                fixture_id=None,
                commissioned_at=prior.commissioned_at,
                decommissioned_at=prior.decommissioned_at,
                persistent_id=prior.persistent_id,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AssetEvent]) -> Asset | None:
    """Replay a stream of events from the empty initial state."""
    state: Asset | None = None
    for event in events:
        state = evolve(state, event)
    return state
