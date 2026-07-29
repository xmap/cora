"""The pilot seed ceremony: give a CORA instance the beamline ingest needs.

`python -m cora.api.pilot_seed` registers, idempotently, the minimum a
deployment must know before `ingest_scan` can record anything: the
beamline root Unit Asset (facility-bound per the anchoring XOR), the
camera Device Asset, its Camera family attachment (whose seed roster
carries Capturing), and one Storage-kind Supply. Inputs are explicit
CLI arguments; the ceremony reads no descriptor. The full
descriptor-reconciling onboarding is a deliberate later slice with its
own trigger (see project_beamline_seeder_design), because 52 of the
descriptor's 53 instances have no production reader in the read-only
pilot and the two things ingest needs are exactly the two the
descriptor cannot provide.

## Identity is per-aggregate, matching each aggregate's locked design

  - Assets: deterministic `uuid5(ASSET_SEED_NAMESPACE,
    "{facility}:{beamline}:asset:{name}")`, path-qualified so no bare
    name is reserved repo-wide, appended at expected_version=0 with
    ConcurrencyError meaning already-seeded.
  - Families: RESOLVED via `family_stream_id(name)`, never defined
    here. Family ids are bare-name-derived by design (a Camera at APS
    and at MAX IV must share one id or Assembly content hashes fork),
    and definitions belong to the seed registry's graduation
    governance.
  - Enclosures: not touched. They are boot-seeded with minted ids and
    an address pre-check precisely because deterministic ids would
    collide with tombstones on re-register.
  - Supplies: minted id; idempotency comes from an address pre-check
    against the supply projection, mirroring the partial-unique
    address that makes deregister-then-re-register legal.

## Why the ceremony drains projections itself

The registration deciders demand facility lookup results that
production fills from projections, and a standalone kernel has no
projection worker. The ceremony therefore runs the same idempotent
bootstrap hooks the app lifespan runs (federation for the
self-Facility, equipment for roles and families) and drains the
relevant projections between stages; without that, a fresh database
refuses every registration with FacilityNotFound.

## What a re-run does

Nothing, loudly. Every instance reports one of: seeded, exists,
retired (the stream folds to Decommissioned; the ceremony never
resurrects a tombstone, since decommission-then-re-register is the
operator's rebind path, not the seeder's), or error. Exit codes: 0
when everything already existed, 2 when anything was seeded, 1 on any
error. A `--dry-run` prints the same report and writes nothing.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from uuid import UUID, uuid5

from cora.equipment._bootstrap import bootstrap_equipment, bootstrap_families
from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import Asset, AssetLifecycle, AssetTier
from cora.equipment.aggregates.asset.events import event_type_name as asset_event_type_name
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.equipment.aggregates.asset.read import load_asset
from cora.equipment.aggregates.family import Affordance, FamilyName
from cora.equipment.aggregates.family._family_registry import family_stream_id
from cora.equipment.aggregates.family.read import load_family
from cora.equipment.features.add_asset_family.command import AddAssetFamily
from cora.equipment.features.add_asset_family.decider import decide as decide_add_family
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.decider import decide as decide_asset
from cora.federation._bootstrap import bootstrap_federation
from cora.federation._projections import register_federation_projections
from cora.federation.adapters.postgres_facility_lookup import PostgresFacilityLookup
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_postgres_kernel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    SystemClock,
    UUIDv7Generator,
)
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.postgres.pool import create_pool
from cora.infrastructure.projection.drain import drain_projections
from cora.infrastructure.projection.worker import ProjectionRegistry
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.infrastructure.schema_version import verify_schema_version
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply._projections import register_supply_projections
from cora.supply.adapters.postgres_supply_lookup import PostgresSupplyLookup
from cora.supply.aggregates.supply.events import event_type_name as supply_event_type_name
from cora.supply.aggregates.supply.events import to_payload as supply_to_payload
from cora.supply.aggregates.supply.state import Supply, SupplyCannotMarkAvailableError, SupplyStatus
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable
from cora.supply.features.mark_supply_available.decider import decide as decide_mark_available
from cora.supply.features.register_supply.command import RegisterSupply
from cora.supply.features.register_supply.decider import decide as decide_supply

#: Namespace for the ceremony's deterministic Asset identities. Path-
#: qualified keys under it ("aps:2-bm:asset:<name>") make re-runs
#: idempotent without reserving bare names repo-wide (the Role/Imager
#: lesson) and keep two beamlines' identically named devices distinct.
ASSET_SEED_NAMESPACE = UUID("6c1f4a52-8f2e-4bb0-9d59-1a4c9be1a23d")

_COMMAND_NAME = "SeedPilotBeamline"

_EXIT_CLEAN = 0
_EXIT_ERROR = 1
_EXIT_SEEDED = 2


def asset_seed_id(facility_code: str, beamline: str, name: str) -> UUID:
    return uuid5(ASSET_SEED_NAMESPACE, f"{facility_code}:{beamline}:asset:{name}")


@dataclass
class _Report:
    lines: list[str]
    seeded: bool = False
    failed: bool = False

    def note(self, outcome: str, subject: str, detail: str = "") -> None:
        suffix = f" ({detail})" if detail else ""
        self.lines.append(f"{outcome:<8} {subject}{suffix}")
        if outcome == "seeded":
            self.seeded = True
        if outcome == "error":
            self.failed = True


async def seed_pilot_beamline(
    *,
    facility_code: str,
    beamline: str,
    root_name: str,
    camera_name: str,
    camera_family_name: str,
    supply_name: str,
    dry_run: bool,
    database_url: str | None = None,
) -> int:
    """Run the ceremony. `database_url` overrides the Settings value so
    the integration tier can point a run at its per-test database; the
    CLI always uses the deployment's own configuration."""
    settings = Settings()
    pool = await create_pool(
        database_url if database_url is not None else settings.database_url,
        min_size=1,
        max_size=4,
    )
    report = _Report(lines=[])
    try:
        await verify_schema_version(pool)
        # The REAL projection-backed lookups, explicitly: the kernel's
        # defaults are test stubs (a synthetic-supply lookup and an
        # empty in-memory facility lookup), and a ceremony that
        # pre-checks idempotency against a stub re-seeds on every run.
        kernel = make_postgres_kernel(
            pool,
            settings=settings,
            clock=SystemClock(),
            id_generator=UUIDv7Generator(),
            authz=AllowAllAuthorize(),
            facility_lookup=PostgresFacilityLookup(pool),
            supply_lookup=PostgresSupplyLookup(pool),
        )

        registry = ProjectionRegistry()
        register_federation_projections(registry, kernel)
        register_equipment_projections(registry, kernel)
        register_supply_projections(registry, kernel)

        # Prerequisites the app lifespan normally seeds. All
        # idempotent; a dry run still runs them so its report reads
        # against a database in the state a real run would see.
        await bootstrap_federation(kernel)
        await bootstrap_equipment(kernel)
        await bootstrap_families(kernel)
        await drain_projections(pool, registry)

        code = FacilityCode(facility_code)
        facility = await kernel.facility_lookup.lookup_by_code(code)
        if facility is None:
            report.note(
                "error",
                f"facility {facility_code}",
                "not found after bootstrap; is SELF_FACILITY_CODE set to this code?",
            )
            return _finish(report, dry_run)

        actor = ActorId(SYSTEM_PRINCIPAL_ID)
        clock = kernel.clock
        ids = kernel.id_generator
        run_correlation_id = ids.new_id()
        family_id = family_stream_id(FamilyName(camera_family_name))

        # Guard the whole point: the camera family must carry Capturing
        # or ingest's Acquisition gate refuses every capture. On a fresh
        # database the roster seed above guarantees it; on an already-
        # seeded database the bootstrap skips existing streams, so an
        # older Camera lacks the affordance until version_family runs.
        family = await load_family(kernel.event_store, family_id)
        if family is None:
            report.note("error", f"family {camera_family_name}", "not seeded; unknown family name")
            return _finish(report, dry_run)
        if Affordance.CAPTURING not in family.affordances:
            report.note(
                "error",
                f"family {camera_family_name}",
                "lacks the Capturing affordance; this database predates the "
                "roster change. Remedy: version_family adding Capturing.",
            )
            return _finish(report, dry_run)
        report.note("exists", f"family {camera_family_name}", "resolved, carries Capturing")

        root_id = asset_seed_id(facility_code, beamline, root_name)
        camera_id = asset_seed_id(facility_code, beamline, camera_name)

        async def seed_asset(asset_id: UUID, command: RegisterAsset, label: str) -> Asset | None:
            state = await load_asset(kernel.event_store, asset_id)
            if state is not None:
                if state.lifecycle is AssetLifecycle.DECOMMISSIONED:
                    report.note("retired", label, "tombstoned stream left untouched")
                    return None
                report.note("exists", label)
                return state
            events = decide_asset(
                state=None,
                command=command,
                now=clock.now(),
                new_id=asset_id,
                commissioned_by=actor,
                facility_lookup_result=facility,
            )
            if dry_run:
                report.note("seeded", label, "dry-run, not written")
                return None
            envelopes = [
                to_new_event(
                    event_type=asset_event_type_name(event),
                    payload=asset_to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=ids.new_id(),
                    command_name=_COMMAND_NAME,
                    correlation_id=run_correlation_id,
                    principal_id=SYSTEM_PRINCIPAL_ID,
                )
                for event in events
            ]
            try:
                await kernel.event_store.append(
                    stream_type="Asset",
                    stream_id=asset_id,
                    expected_version=0,
                    events=envelopes,
                )
            except ConcurrencyError:
                report.note("exists", label, "raced another writer; already present")
                return await load_asset(kernel.event_store, asset_id)
            report.note("seeded", label)
            return await load_asset(kernel.event_store, asset_id)

        root = await seed_asset(
            root_id,
            RegisterAsset(
                name=root_name,
                tier=AssetTier.UNIT,
                parent_id=None,
                facility_code=facility_code,
            ),
            f"asset {root_name} (Unit root)",
        )

        camera = await seed_asset(
            camera_id,
            RegisterAsset(
                name=camera_name,
                tier=AssetTier.DEVICE,
                parent_id=root_id,
                facility_code=None,
            ),
            f"asset {camera_name} (Device)",
        )

        # Family attachment: strict-not-idempotent decider, so fold
        # first. A family absent from the folded set is treated as this
        # ceremony completing its own interrupted work and attached. The
        # design memo's removed-by-operator discriminator is NOT
        # implementable from folded state (the fold keeps no removal
        # history), so an operator who deliberately detached the family
        # will see it re-attach on the next run; acceptable for the
        # pilot camera, revisited if a real detach case appears.
        if camera is not None:
            if family_id in camera.family_ids:
                report.note("exists", f"{camera_name} family attachment")
            elif dry_run:
                report.note("seeded", f"{camera_name} family attachment", "dry-run, not written")
            else:
                current_state, current_version = await _load_asset_with_version(kernel, camera_id)
                attach_events = decide_add_family(
                    state=current_state,
                    command=AddAssetFamily(asset_id=camera_id, family_id=family_id),
                    now=clock.now(),
                )
                attach_envelopes = [
                    to_new_event(
                        event_type=asset_event_type_name(event),
                        payload=asset_to_payload(event),
                        occurred_at=event.occurred_at,
                        event_id=ids.new_id(),
                        command_name=_COMMAND_NAME,
                        correlation_id=run_correlation_id,
                        principal_id=SYSTEM_PRINCIPAL_ID,
                    )
                    for event in attach_events
                ]
                await kernel.event_store.append(
                    stream_type="Asset",
                    stream_id=camera_id,
                    expected_version=current_version,
                    events=attach_envelopes,
                )
                report.note("seeded", f"{camera_name} family attachment")

        # Storage supply: minted id, address-pre-checked idempotency.
        supplies_by_kind = await kernel.supply_lookup.find_supplies_by_kind(
            kinds=frozenset({"Storage"})
        )
        existing_storage = [
            supply
            for supply in supplies_by_kind.get("Storage", [])
            if supply.name == supply_name and supply.facility_code == facility_code
        ]
        supply_id: UUID | None = None
        if existing_storage:
            supply_id = existing_storage[0].supply_id
            report.note("exists", f"supply {supply_name} (Storage)")
        elif dry_run:
            report.note("seeded", f"supply {supply_name} (Storage)", "dry-run, not written")
        else:
            supply_id = ids.new_id()
            supply_events = decide_supply(
                state=None,
                command=RegisterSupply(
                    kind="Storage",
                    name=supply_name,
                    facility_code=facility_code,
                ),
                now=clock.now(),
                new_id=supply_id,
                triggered_by=actor,
                facility_lookup_result=facility,
                asset_lookup_result=None,
            )
            supply_envelopes = [
                to_new_event(
                    event_type=supply_event_type_name(event),
                    payload=supply_to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=ids.new_id(),
                    command_name=_COMMAND_NAME,
                    correlation_id=run_correlation_id,
                    principal_id=SYSTEM_PRINCIPAL_ID,
                )
                for event in supply_events
            ]
            await kernel.event_store.append(
                stream_type="Supply",
                stream_id=supply_id,
                expected_version=0,
                events=supply_envelopes,
            )
            report.note("seeded", f"supply {supply_name} (Storage)")

        # Availability: a freshly registered Supply is not Available,
        # and the run-preflight gates plus the legacy-Distribution
        # backfill (`SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE`) only
        # accept an Available one, so a supply left merely registered is
        # half-seeded. The transition decider is strict, so fold first
        # and only mark when the status still permits it; any other
        # status (Degraded, Unavailable) is an operator's statement and
        # stays hands-off.
        if supply_id is not None:
            supply_state, supply_version = await _load_supply_with_version(kernel, supply_id)
            if supply_state is None:
                report.note("error", f"supply {supply_name} availability", "stream missing")
            elif supply_state.status is SupplyStatus.AVAILABLE:
                report.note("exists", f"supply {supply_name} availability")
            elif dry_run:
                report.note("seeded", f"supply {supply_name} availability", "dry-run, not written")
            else:
                try:
                    mark_events = decide_mark_available(
                        state=supply_state,
                        command=MarkSupplyAvailable(
                            supply_id=supply_id,
                            reason="seeded by the pilot ceremony",
                        ),
                        now=clock.now(),
                        triggered_by=actor,
                    )
                except SupplyCannotMarkAvailableError as exc:
                    report.note("retired", f"supply {supply_name} availability", str(exc))
                else:
                    mark_envelopes = [
                        to_new_event(
                            event_type=supply_event_type_name(event),
                            payload=supply_to_payload(event),
                            occurred_at=event.occurred_at,
                            event_id=ids.new_id(),
                            command_name=_COMMAND_NAME,
                            correlation_id=run_correlation_id,
                            principal_id=SYSTEM_PRINCIPAL_ID,
                        )
                        for event in mark_events
                    ]
                    await kernel.event_store.append(
                        stream_type="Supply",
                        stream_id=supply_id,
                        expected_version=supply_version,
                        events=mark_envelopes,
                    )
                    report.note("seeded", f"supply {supply_name} availability")

        _ = root
        if not dry_run:
            # Leave the projections current so a re-run's supply
            # pre-check (and the app, before its worker catches up)
            # sees what this run wrote.
            await drain_projections(pool, registry)
        return _finish(report, dry_run)
    except Exception as exc:  # the ceremony is a CLI: name it, exit 1
        report.note("error", "ceremony", str(exc))
        return _finish(report, dry_run)
    finally:
        await pool.close()


async def _load_asset_with_version(kernel: Kernel, asset_id: UUID) -> tuple[Asset | None, int]:
    from cora.equipment.aggregates.asset.events import from_stored
    from cora.equipment.aggregates.asset.evolver import fold

    stored, version = await kernel.event_store.load("Asset", asset_id)
    events = [from_stored(event) for event in stored]
    return fold(events), version


async def _load_supply_with_version(kernel: Kernel, supply_id: UUID) -> tuple[Supply | None, int]:
    from cora.supply.aggregates.supply.events import from_stored
    from cora.supply.aggregates.supply.evolver import fold

    stored, version = await kernel.event_store.load("Supply", supply_id)
    events = [from_stored(event) for event in stored]
    return fold(events), version


def _finish(report: _Report, dry_run: bool) -> int:
    header = "pilot seed (dry run)" if dry_run else "pilot seed"
    print(header)
    for line in report.lines:
        print(f"  {line}")
    if report.failed:
        return _EXIT_ERROR
    return _EXIT_SEEDED if report.seeded else _EXIT_CLEAN


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, separate from `main` so tests can pin the
    defaults and flags without touching a database.

    The facility default is `cora`, matching `SELF_FACILITY_CODE`'s own
    default: the ceremony registers under the facility this deployment
    self-seeded, and a mismatch is a loud FacilityNotFound rather than a
    quietly wrong registration.
    """
    parser = argparse.ArgumentParser(
        prog="python -m cora.api.pilot_seed",
        description=(
            "Register the minimum a deployment needs before ingest_scan "
            "can record: the beamline root Unit, the camera Device with "
            "its Capturing-bearing family, and a Storage supply. "
            "Idempotent; re-runs report and change nothing."
        ),
    )
    parser.add_argument("--facility-code", default="cora")
    parser.add_argument("--beamline", default="2-bm")
    parser.add_argument("--root-name", default="2-BM")
    parser.add_argument("--camera-name", default="Camera")
    parser.add_argument("--camera-family-name", default="Camera")
    parser.add_argument("--supply-name", default="analysis-tier")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(
        seed_pilot_beamline(
            facility_code=args.facility_code,
            beamline=args.beamline,
            root_name=args.root_name,
            camera_name=args.camera_name,
            camera_family_name=args.camera_family_name,
            supply_name=args.supply_name,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
