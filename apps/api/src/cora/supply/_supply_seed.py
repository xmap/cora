"""Supply BC lifespan hook: seed the Supplies a monitor observes.

Caller-driven: one Supply per name handed in, registered under
`self_facility_code`. An empty set is a no-op, so a generic boot registers
nothing. Mirrors `cora.enclosure._enclosure_seed` in shape and shares its
constraints.

## The caller names the resources, not this module

The names arrive as an argument rather than being read from a
substrate-specific setting. An earlier version read
`Settings.bleps_supply_channels` directly, which put a BLEPS token inside
`cora.supply` and broke this BC's own rule that "the runtime never
touches substrate-specific symbols" (`ports/supply_observer.py`). The
composition root knows about BLEPS; the Supply BC knows about Supplies.

## Registered, deliberately NOT marked Available

A seeded Supply is left at `Unknown`. CORA has observed nothing about the
cooling water at boot, and `Unknown` is what "no observation yet" means;
the `SupplyStatus` docstring calls the optimistic-Available default an
anti-pattern across all three research corpora, and this is exactly that
case. The monitor can drive `Unknown` straight to `Unavailable` on a
trip, so nothing is lost by waiting.

This deliberately differs from `cora.api.pilot_seed`, which DOES mark its
Storage supply Available. That one has to: the run pre-flight gate and
the legacy-Distribution backfill both require an Available Storage
supply, so a merely-registered one is half-seeded. Nothing requires an
Available CoolingWater or Vacuum supply today, and the hazard runs the
other way. The gate is default-strict (`Degraded` does not pass), so if a
Method later declares `needed_supplies: [CoolingWater]`, an Available-at-
boot Supply would pass a gate on a resource CORA has never looked at. An
operator declaring it Available via `mark_supply_available` is the
first-observation gesture that exists for this, and it means a person
actually looked.

## Kind is derived from the Supply name, not configured

The `kind` comes from a small name-to-kind table below rather than from
config, because `Supply.kind` participates in the pre-flight gate's
matching and a typo there would silently create a second, unmatched
resource. Two kinds are wired, which is what the 2-BM BLEPS taxonomy
needs; a third deployment naming its resources differently should extend
the table rather than push the choice into an env var.

## Idempotency without deterministic ids

Supply ids are MINTED and the four-tuple address is reusable across
deregister / re-register, so this cannot use the deterministic-id plus
ConcurrencyError-swallow trick. It pre-checks the live address via
`SupplyLookup.find_supplies_by_kind` and reuses a match's id, exactly as
`pilot_seed` does for its Storage supply.

LOAD-BEARING ORDER (Postgres): the supply projection MUST be drained
before this hook runs, or the pre-check misses on every boot and the
seeder appends a duplicate genesis event each time. The lifespan does
that drain, mirroring the enclosure hook.

Returns `{supply_name: supply_id}` for every configured Supply (freshly
seeded or pre-existing) so the monitor loop resolves codes to ids without
depending on projection-catch-up timing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyRegistered,
    event_type_name,
    to_payload,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports.supply_lookup import SupplyLookupResult

_COMMAND_NAME = "RegisterSupply"
_STREAM_TYPE = "Supply"
# Registration has no Monitor counterpart: it is always operator-driven,
# and a system bootstrap write is attributed to the system principal in
# that role. Same convention as the enclosure and clearance-template
# seeders.
_TRIGGER_OPERATOR = "Operator"

# Supply name -> Supply.kind. See the module docstring for why this is a
# table here rather than a config field.
_KIND_BY_NAME: dict[str, str] = {
    "2-BM cooling water": "CoolingWater",
    "2-BM beamline vacuum": "Vacuum",
}

_log = get_logger(__name__)


def supply_kind_from_name(name: str) -> str | None:
    """The `Supply.kind` for a configured supply name, or None if unknown.

    An unknown name is a configuration error, not a reason to invent a
    kind: a guessed kind would register a resource that the pre-flight
    gate can never match against a Method's `needed_supplies`.
    """
    return _KIND_BY_NAME.get(name)


async def seed_observed_supplies(deps: Kernel, *, supply_names: frozenset[str]) -> dict[str, UUID]:
    """Register each named Supply if absent; return name -> id for all of them."""
    names: list[str] = sorted(supply_names)
    if not names:
        return {}

    facility_code = deps.settings.self_facility_code
    wanted_kinds = frozenset(
        kind for kind in (supply_kind_from_name(name) for name in names) if kind is not None
    )
    existing_by_kind: Mapping[str, Sequence[SupplyLookupResult]] = (
        await deps.supply_lookup.find_supplies_by_kind(kinds=wanted_kinds) if wanted_kinds else {}
    )

    seeded: dict[str, UUID] = {}
    for name in names:
        kind = supply_kind_from_name(name)
        if kind is None:
            _log.warning("supply_seed.unknown_supply_name", supply_name=name)
            continue

        match = next(
            (
                supply
                for supply in existing_by_kind.get(kind, [])
                if supply.name == name and supply.facility_code == facility_code
            ),
            None,
        )
        if match is not None:
            seeded[name] = match.supply_id
            continue

        supply_id = deps.id_generator.new_id()
        event = SupplyRegistered(
            supply_id=supply_id,
            kind=kind,
            name=name,
            facility_code=FacilityCode(facility_code),
            trigger=_TRIGGER_OPERATOR,
            triggered_by=ActorId(SYSTEM_PRINCIPAL_ID),
            occurred_at=deps.clock.now(),
            containing_asset_id=None,
        )
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=supply_id,
            expected_version=0,
            events=[
                to_new_event(
                    event_type=event_type_name(event),
                    payload=to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=deps.id_generator.new_id(),
                    command_name=_COMMAND_NAME,
                    correlation_id=deps.id_generator.new_id(),
                    causation_id=None,
                    principal_id=SYSTEM_PRINCIPAL_ID,
                )
            ],
        )
        seeded[name] = supply_id
        _log.info("supply_seed.registered", supply_name=name, kind=kind)

    return seeded


__all__ = ["seed_observed_supplies", "supply_kind_from_name"]
