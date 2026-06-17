"""Enclosure BC lifespan hook: seed the deployment's permit-gated enclosures.

Config-driven: one Enclosure per key in `Settings.enclosure_permit_pvs`,
registered under `self_facility_code`. Empty config (the default) is a
no-op, so a generic boot registers nothing; only a deployment that
configures `ENCLOSURE_PERMIT_PVS` (e.g. 2-BM) seeds its hutches.

## Idempotency without deterministic ids

Enclosure ids are MINTED, not address-derived, and the
`(facility_code, name)` address is reusable across the
decommission / re-register lifecycle (the projection's partial-unique
index is on Active rows only). So this seeder cannot use the
deterministic-id + ConcurrencyError-swallow trick that
`seed_clearance_templates` uses. Instead it pre-checks the live address
via `EnclosureLookup.lookup_by_name`: if an Active enclosure already
exists at `(facility, name)`, reuse its id; otherwise mint a fresh one
and register. A decommissioned enclosure leaves no Active row, so it is
correctly re-seeded with a NEW id on the next boot, preserving the
decommission/re-register flow (a deterministic id would wrongly collide
with the tombstoned stream and refuse the re-seed).

LOAD-BEARING ORDER (Postgres): the enclosure projection MUST be drained
before this hook runs, so `lookup_by_name` reflects prior boots; the
lifespan does that drain (mirrors the federation drain before
`seed_clearance_templates`). Without it the pre-check misses and the
seeder would append a duplicate genesis event every boot.

## Raw write + in-memory mirror

The genesis `EnclosureRegistered` event is written raw via
`append_streams` with the `SYSTEM_PRINCIPAL_ID` envelope (the bootstrap
convention shared with `seed_clearance_templates` /
`seed_run_debriefer_agent`), bypassing the operator authorize gate. The
seeded row is mirrored into the in-memory `EnclosureLookup` for the
test / in-memory AppEnv, where the projection worker that catches up the
Postgres lookup does not run (mirrors
`_seed_in_memory_clearance_template_lookup`).

Returns `{enclosure_name: enclosure_id}` for every configured enclosure
(freshly seeded or pre-existing) so the permit monitor loop resolves
names to ids without depending on projection-catch-up timing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    EnclosureRegistered,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import ConcurrencyError, StreamAppend
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel

_STREAM_TYPE = "Enclosure"
_COMMAND_NAME = "seed_enclosures"

_log = get_logger(__name__)


async def seed_enclosures(kernel: Kernel) -> dict[str, UUID]:
    """Seed the configured enclosures (idempotent); return `{name: id}`.

    No-op returning `{}` when `enclosure_permit_pvs` is empty.
    """
    name_to_id: dict[str, UUID] = {}
    names = sorted(kernel.settings.enclosure_permit_pvs)
    if not names:
        return name_to_id
    facility_code = kernel.settings.self_facility_code
    for name in names:
        name_to_id[name] = await _seed_one_enclosure(kernel, facility_code=facility_code, name=name)
    return name_to_id


async def _seed_one_enclosure(kernel: Kernel, *, facility_code: str, name: str) -> UUID:
    existing = await kernel.enclosure_lookup.lookup_by_name(facility_code=facility_code, name=name)
    if existing is not None:
        _log.info(
            "enclosure_seed.already_present",
            enclosure_id=str(existing.enclosure_id),
            facility_code=facility_code,
            name=name,
        )
        return existing.enclosure_id

    now = kernel.clock.now()
    enclosure_id = EnclosureId(kernel.id_generator.new_id())
    correlation_id = kernel.id_generator.new_id()

    registered = EnclosureRegistered(
        enclosure_id=enclosure_id,
        name=name,
        facility_code=FacilityCode(facility_code),
        registered_by=ActorId(SYSTEM_PRINCIPAL_ID),
        occurred_at=now,
    )
    new_event = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=now,
        event_id=kernel.id_generator.new_id(),
        command_name=_COMMAND_NAME,
        correlation_id=correlation_id,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )

    try:
        await kernel.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=_STREAM_TYPE,
                    stream_id=enclosure_id,
                    expected_version=0,
                    events=[new_event],
                ),
            ]
        )
    except ConcurrencyError:
        # The minted id is random, so a genuine collision is effectively
        # impossible; treat a lost race as already-seeded and resolve the
        # live id from the address.
        resolved = await kernel.enclosure_lookup.lookup_by_name(
            facility_code=facility_code, name=name
        )
        return resolved.enclosure_id if resolved is not None else enclosure_id

    _log.info(
        "enclosure_seed.created",
        enclosure_id=str(enclosure_id),
        facility_code=facility_code,
        name=name,
    )
    _seed_in_memory_enclosure_lookup(kernel, enclosure_id, facility_code, name)
    return enclosure_id


def _seed_in_memory_enclosure_lookup(
    kernel: Kernel, enclosure_id: UUID, facility_code: str, name: str
) -> None:
    """Mirror a freshly-seeded enclosure into the in-memory EnclosureLookup.

    Production wires `PostgresEnclosureLookup` (reads the projection the
    worker catches up), which has no `register`; this is a no-op there.
    The in-memory AppEnv / tests wire `InMemoryEnclosureLookup`, whose
    lookup has no event-store subscription, so without this the seeded
    enclosure is invisible to the monitor loop's resolution in-process.
    Duck-typed on `.register` per the `_seed_in_memory_clearance_template_lookup`
    precedent; genesis status is `Unknown` / `Active`.
    """
    register = getattr(kernel.enclosure_lookup, "register", None)
    if register is None:
        return
    register(
        enclosure_id=enclosure_id,
        name=name,
        permit_status="Unknown",
        lifecycle="Active",
        facility_code=facility_code,
    )


__all__ = ["seed_enclosures"]
