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
`drawing` AND `model_id` through from prior state. Constructing
`Asset(id=..., name=..., level=..., parent_id=..., lifecycle=...)`
without explicitly passing them would silently WIPE the fields to
their defaults (empty frozenset / NOMINAL / empty dict / empty
frozenset / None / None). `family_ids` was added with a default
solely for additive-state forward compatibility on genesis events;
`condition`, `settings`, `ports`, `drawing`, and `model_id`
followed the same additive pattern. Transition arms must
explicitly carry all six. `model_id` is set ONCE at registration
per the model-binding design memo (Lock A) and never changes
post-genesis, but transition arms still must carry it forward
like any other Asset field. Pinned by
`test_evolve_<transition>_preserves_capabilities`,
`test_evolve_<transition>_preserves_condition`,
`test_evolve_<transition>_preserves_settings`,
`test_evolve_<transition>_preserves_ports`,
`test_evolve_<transition>_preserves_drawing`, and
`test_evolve_<transition>_preserves_model_id` for each transition.

Transition events applied to empty state raise ValueError: they
can never appear before `AssetRegistered` in a well-formed stream.
The `require_state` helper keeps the per-arm bodies short
(precedent locked by Subject's evolver).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetDecommissioned,
    AssetDegraded,
    AssetEvent,
    AssetFamilyAdded,
    AssetFamilyRemoved,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetMaintenanceExited,
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
            drawing=drawing,
            model_id=model_id,
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
                # family_ids defaults to empty frozenset; condition
                # defaults to NOMINAL. Additive-state pattern: both
                # default-via-state so legacy streams without these
                # fields fold cleanly without an upcaster.
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
            )
        case AssetDecommissioned():
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
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AssetEvent]) -> Asset | None:
    """Replay a stream of events from the empty initial state."""
    state: Asset | None = None
    for event in events:
        state = evolve(state, event)
    return state
