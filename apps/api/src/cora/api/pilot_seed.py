"""The pilot seed ceremony: give a CORA instance what the 2-BM pilot needs.

`python -m cora.api.pilot_seed` registers, idempotently, two things a
deployment must know before it can do anything real: what `ingest_scan`
needs to record a capture, and what `start_run` needs to have a real
`plan_id` to bind to. Inputs are explicit CLI arguments; the ceremony
reads no descriptor. The full descriptor-reconciling onboarding is a
deliberate later slice with its own trigger (see
project_beamline_seeder_design), because 52 of the descriptor's 53
instances have no production reader in the read-only pilot and the
things this ceremony needs are exactly the ones the descriptor cannot
provide.

Registers:
  - the beamline root Unit Asset (facility-bound per the anchoring
    XOR), a camera Device Asset with its Camera family attachment
    (whose seed roster carries Capturing), and one Storage-kind Supply
    -- what `ingest_scan` needs.
  - a StationShutter Device Asset and a second camera Device Asset (the
    5 MP unit `docs/deployments/2-bm/recipes.md`'s `dark_field` /
    `flat_field` recipes actually target, distinct from the first
    camera), each declaring `located_in_enclosure_id` for `2-BM-B`
    (resolved by name, never hardcoded -- see
    `docs/deployments/2-bm/enclosures.md`), plus the Capability ->
    Method -> Practice -> Plan chain for those same two recipes, bound
    to the two new Assets -- what `start_run` needs, including the
    Enclosure-permit gate: `located_in_enclosure_id` is genesis-only
    (no update command exists), and a Run whose scoped Assets declare
    NONE is Permit-by-default, so leaving it unset is a silent gate
    skip, not a cosmetic gap. `energy_setting` and `hexapod_reboot`
    stay unregistered: `recipes.md` marks both "design, pending
    executor", so a Plan for either would fail on its first conduct
    step.

  A ONE-TIME migration lives permanently in this file: the first
  StationShutter/Camera registration (pre-2026-08-14) had no
  `located_in_enclosure_id`. Fixing that on an already-registered
  Asset means decommission + re-register (Lock A precedent, same as
  `controller_id`); the two Plans binding the old ids are deprecated
  and replaced by `_v2` Plans binding the new ones. Capability /
  Method / Practice are untouched -- none reference a specific Asset
  id. A deployment seeded fresh after this change never sees the old
  names at all; it goes straight to the located `_v2` registration.

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
  - Enclosures: RESOLVED via `seed_enclosures(kernel)`, the same
    idempotent seed the real app's boot lifespan runs -- never
    created with a ceremony-local id. Minted at boot, with an address
    pre-check, precisely because deterministic ids would collide with
    tombstones on re-register.
  - Supplies: minted id; idempotency comes from an address pre-check
    against the supply projection, mirroring the partial-unique
    address that makes deregister-then-re-register legal.

## Why the ceremony drains projections itself

The registration deciders demand facility lookup results that
production fills from projections, and a standalone kernel has no
projection worker. The ceremony therefore runs the same idempotent
bootstrap hooks the app lifespan runs (federation for the
self-Facility, equipment for roles and families, enclosure for
2-BM-A / 2-BM-B) and drains the relevant projections between stages;
without that, a fresh database refuses every registration with
FacilityNotFound.

## What a re-run does

Nothing, loudly, for everything except the one deliberate migration
this file performs on itself (see the `_v2` Asset/Plan registrations
above): every OTHER instance reports one of: seeded, exists, retired
(the stream folds to Decommissioned; the ceremony never resurrects a
tombstone read on a name it did not itself just decommission, since
decommission-then-re-register under a NEW id is the only rebind path,
never a re-append to the old one), or error. Exit codes: 0
when everything already existed, 2 when anything was seeded, 1 on any
error. A `--dry-run` prints the same report and writes nothing.
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID, uuid5

from cora.enclosure._enclosure_seed import seed_enclosures
from cora.enclosure._projections import register_enclosure_projections
from cora.enclosure.adapters.postgres_enclosure_lookup import PostgresEnclosureLookup
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
from cora.equipment.features.decommission_asset.command import DecommissionAsset
from cora.equipment.features.decommission_asset.context import DecommissionAssetContext
from cora.equipment.features.decommission_asset.decider import decide as decide_decommission_asset
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
from cora.recipe.aggregates.capability import Capability, ExecutorShape
from cora.recipe.aggregates.capability.events import event_type_name as capability_event_type_name
from cora.recipe.aggregates.capability.events import to_payload as capability_to_payload
from cora.recipe.aggregates.capability.read import load_capability
from cora.recipe.aggregates.method import ExecutionPattern, Method
from cora.recipe.aggregates.method.events import event_type_name as method_event_type_name
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.method.read import load_method
from cora.recipe.aggregates.plan.events import event_type_name as plan_event_type_name
from cora.recipe.aggregates.plan.events import to_payload as plan_to_payload
from cora.recipe.aggregates.plan.read import load_plan
from cora.recipe.aggregates.plan.state import PlanStatus
from cora.recipe.aggregates.practice.events import event_type_name as practice_event_type_name
from cora.recipe.aggregates.practice.events import to_payload as practice_to_payload
from cora.recipe.aggregates.practice.read import load_practice
from cora.recipe.features.define_capability.command import DefineCapability
from cora.recipe.features.define_capability.decider import decide as decide_capability
from cora.recipe.features.define_method.command import DefineMethod
from cora.recipe.features.define_method.decider import decide as decide_method
from cora.recipe.features.define_plan.command import DefinePlan
from cora.recipe.features.define_plan.context import PlanBindingContext
from cora.recipe.features.define_plan.decider import decide as decide_plan
from cora.recipe.features.define_practice.command import DefinePractice
from cora.recipe.features.define_practice.decider import decide as decide_practice
from cora.recipe.features.deprecate_plan.command import DeprecatePlan
from cora.recipe.features.deprecate_plan.decider import decide as decide_deprecate_plan
from cora.shared.deprecation import DeprecationReason
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

if TYPE_CHECKING:
    from cora.recipe.aggregates.plan import Plan
    from cora.recipe.aggregates.practice import Practice

#: Namespace for the ceremony's deterministic Asset identities. Path-
#: qualified keys under it ("aps:2-bm:asset:<name>") make re-runs
#: idempotent without reserving bare names repo-wide (the Role/Imager
#: lesson) and keep two beamlines' identically named devices distinct.
ASSET_SEED_NAMESPACE = UUID("6c1f4a52-8f2e-4bb0-9d59-1a4c9be1a23d")

#: Namespace for the ceremony's deterministic Recipe-BC identities
#: (Capability / Method / Practice / Plan). Recipe aggregates have no
#: `uuid5` registry of their own (unlike Family's bare-name-derived
#: ids), and this deployment-specific ladder is not cross-facility
#: vocabulary, so it is facility+beamline-qualified like Assets, under
#: its own namespace rather than reusing `ASSET_SEED_NAMESPACE`.
RECIPE_SEED_NAMESPACE = UUID("48eb0d48-8fc2-482c-9e9e-d3547b1ff37b")

_COMMAND_NAME = "SeedPilotBeamline"

_EXIT_CLEAN = 0
_EXIT_ERROR = 1
_EXIT_SEEDED = 2

_T = TypeVar("_T")


def asset_seed_id(facility_code: str, beamline: str, name: str) -> UUID:
    return uuid5(ASSET_SEED_NAMESPACE, f"{facility_code}:{beamline}:asset:{name}")


def recipe_seed_id(facility_code: str, beamline: str, kind: str, name: str) -> UUID:
    return uuid5(RECIPE_SEED_NAMESPACE, f"{facility_code}:{beamline}:{kind}:{name}")


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
    shutter_name: str = "StationShutter",
    acquisition_camera_name: str = "AcquisitionCamera",
    rotary_stage_name: str = "RotaryStage",
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
            enclosure_lookup=PostgresEnclosureLookup(pool),
        )

        registry = ProjectionRegistry()
        register_federation_projections(registry, kernel)
        register_equipment_projections(registry, kernel)
        register_supply_projections(registry, kernel)
        register_enclosure_projections(registry, kernel)

        # Prerequisites the app lifespan normally seeds. All
        # idempotent; a dry run still runs them so its report reads
        # against a database in the state a real run would see.
        await bootstrap_federation(kernel)
        await bootstrap_equipment(kernel)
        await bootstrap_families(kernel)
        # Same function the real app's own boot lifespan calls; on
        # arcturus (already seeded) this just resolves the existing
        # 2-BM-A / 2-BM-B ids, on a fresh database it seeds them for
        # real. Never hardcode these ids: they are minted at boot, not
        # deterministic (unlike Assets), so a stale literal would
        # silently resolve nothing on a re-seeded database.
        enclosure_ids_by_name = await seed_enclosures(kernel)
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

        enclosure_b_id = enclosure_ids_by_name.get("2-BM-B")
        if enclosure_b_id is None:
            report.note(
                "error",
                "enclosure 2-BM-B",
                "not configured; is ENCLOSURE_PERMIT_PVS set for this deployment?",
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
        async def attach_family(
            asset: Asset | None, asset_id: UUID, family_id: UUID, label: str
        ) -> None:
            if asset is None:
                return
            if family_id in asset.family_ids:
                report.note("exists", f"{label} family attachment")
                return
            if dry_run:
                report.note("seeded", f"{label} family attachment", "dry-run, not written")
                return
            current_state, current_version = await _load_asset_with_version(kernel, asset_id)
            attach_events = decide_add_family(
                state=current_state,
                command=AddAssetFamily(asset_id=asset_id, family_id=family_id),
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
                stream_id=asset_id,
                expected_version=current_version,
                events=attach_envelopes,
            )
            report.note("seeded", f"{label} family attachment")

        await attach_family(camera, camera_id, family_id, camera_name)

        # ----- Recipe BC prerequisite Assets: what dark_field / flat_field
        # actually target, per docs/deployments/2-bm/recipes.md -----

        async def decommission_if_present(old_id: UUID, label: str) -> None:
            """One-time migration step, permanent in this file: the first
            registration of this Asset (pre-2026-08-14) had no
            `located_in_enclosure_id`. No-op when the old stream never
            existed (a fresh deployment goes straight to the located `_v2`
            registration below and never sees this Asset name at all) or
            is already Decommissioned (a prior run already migrated it).
            """
            old_state, old_version = await _load_asset_with_version(kernel, old_id)
            if old_state is None:
                return
            if old_state.lifecycle is AssetLifecycle.DECOMMISSIONED:
                report.note("exists", f"asset {label} (v1) decommissioned")
                return
            if dry_run:
                report.note("seeded", f"asset {label} (v1) decommissioned", "dry-run, not written")
                return
            decommission_events = decide_decommission_asset(
                state=old_state,
                command=DecommissionAsset(
                    asset_id=old_id,
                    reason=(
                        "relocated: located_in_enclosure_id was never set at genesis; "
                        "superseded by a 2-BM-B-located registration"
                    ),
                ),
                context=DecommissionAssetContext(currently_installed_at_mount_id=None),
                now=clock.now(),
                decommissioned_by=actor,
            )
            decommission_envelopes = [
                to_new_event(
                    event_type=asset_event_type_name(event),
                    payload=asset_to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=ids.new_id(),
                    command_name=_COMMAND_NAME,
                    correlation_id=run_correlation_id,
                    principal_id=SYSTEM_PRINCIPAL_ID,
                )
                for event in decommission_events
            ]
            await kernel.event_store.append(
                stream_type="Asset",
                stream_id=old_id,
                expected_version=old_version,
                events=decommission_envelopes,
            )
            report.note("seeded", f"asset {label} (v1) decommissioned")

        await decommission_if_present(
            asset_seed_id(facility_code, beamline, shutter_name), shutter_name
        )
        await decommission_if_present(
            asset_seed_id(facility_code, beamline, acquisition_camera_name),
            acquisition_camera_name,
        )

        # Located registration. New deterministic ids under a versioned
        # SEED KEY only (asset_seed_id hashes on this key, not on
        # RegisterAsset.name): the v1 id above is no longer at
        # expected_version=0 once decommissioned, so this ceremony cannot
        # reuse it. `RegisterAsset(name=...)` keeps the clean, unsuffixed
        # display name; "_v2" exists only in the id-derivation key, never
        # operator-visible.
        shutter_id = asset_seed_id(facility_code, beamline, f"{shutter_name}_v2")
        acquisition_camera_id = asset_seed_id(
            facility_code, beamline, f"{acquisition_camera_name}_v2"
        )

        shutter = await seed_asset(
            shutter_id,
            RegisterAsset(
                name=shutter_name,
                tier=AssetTier.DEVICE,
                parent_id=root_id,
                facility_code=None,
                located_in_enclosure_id=enclosure_b_id,
            ),
            f"asset {shutter_name} (Device, 2-BM-B)",
        )
        acquisition_camera = await seed_asset(
            acquisition_camera_id,
            RegisterAsset(
                name=acquisition_camera_name,
                tier=AssetTier.DEVICE,
                parent_id=root_id,
                facility_code=None,
                located_in_enclosure_id=enclosure_b_id,
            ),
            f"asset {acquisition_camera_name} (Device, 2-BM-B)",
        )

        # No legacy un-located registration to migrate away from (unlike
        # shutter/camera): this is a brand-new Asset, so a plain
        # (unsuffixed) seed key is correct, matching fly_scan's own Plan
        # using `_v1` rather than `_v2`.
        rotary_stage_id = asset_seed_id(facility_code, beamline, rotary_stage_name)
        rotary_stage = await seed_asset(
            rotary_stage_id,
            RegisterAsset(
                name=rotary_stage_name,
                tier=AssetTier.DEVICE,
                parent_id=root_id,
                facility_code=None,
                located_in_enclosure_id=enclosure_b_id,
            ),
            f"asset {rotary_stage_name} (Device, 2-BM-B)",
        )

        shutter_family_id = family_stream_id(FamilyName("Shutter"))
        shutter_family = await load_family(kernel.event_store, shutter_family_id)
        if shutter_family is None:
            report.note("error", "family Shutter", "not seeded; unknown family name")
            return _finish(report, dry_run)
        report.note("exists", "family Shutter")

        # RotaryStage is a globally-bootstrapped family (see
        # `_family_seed_registry.py`), same precondition as Shutter above.
        # Continuous sample rotation is the defining feature of a real
        # fly-scan (docs/deployments/2-bm/techniques.md); the fly_scan
        # recipe below is the only caller that needs this family/Asset.
        rotary_family_id = family_stream_id(FamilyName("RotaryStage"))
        rotary_family = await load_family(kernel.event_store, rotary_family_id)
        if rotary_family is None:
            report.note("error", "family RotaryStage", "not seeded; unknown family name")
            return _finish(report, dry_run)
        report.note("exists", "family RotaryStage")

        await attach_family(shutter, shutter_id, shutter_family_id, shutter_name)
        await attach_family(
            acquisition_camera, acquisition_camera_id, family_id, acquisition_camera_name
        )
        await attach_family(rotary_stage, rotary_stage_id, rotary_family_id, rotary_stage_name)
        # Reload: `attach_family` writes the attachment but returns nothing,
        # and the Plan step below needs each Asset's CURRENT family_ids
        # (the Recipe-BC family-superset check reads them), not the
        # pre-attachment snapshot `seed_asset` returned above.
        shutter = await load_asset(kernel.event_store, shutter_id)
        acquisition_camera = await load_asset(kernel.event_store, acquisition_camera_id)
        rotary_stage = await load_asset(kernel.event_store, rotary_stage_id)

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

        # ----- Recipe BC: Capability -> Method -> Practice -> Plan ceremony -----
        #
        # A real Run at 2-BM needs a valid plan_id (`start_run` walks
        # Plan -> Practice -> Method -> Capability); nothing here has ever
        # been registered. This registers exactly the two "conductible
        # today" recipes from docs/deployments/2-bm/recipes.md
        # (dark_field, flat_field, both reusing the registered `collect`
        # action body) against the StationShutter + acquisition-camera
        # Assets seeded above.

        async def seed_genesis(
            *,
            stream_type: str,
            state: _T | None,
            decide_thunk: Callable[[], Sequence[Any]],
            event_type_name_fn: Callable[[Any], str],
            to_payload_fn: Callable[[Any], dict[str, Any]],
            stream_id: UUID,
            label: str,
            reload: Callable[[], Awaitable[_T | None]],
        ) -> _T | None:
            """Genesis-only append for a Recipe BC aggregate, mirroring
            `seed_asset`'s shape (state=None check, decide, serialize,
            append at expected_version=0, ConcurrencyError means already
            present).

            Unlike `seed_asset`, `dry_run` is checked BEFORE calling
            `decide_thunk`: a cross-aggregate decider here (Method needs
            Capability, Plan needs Practice + Method + Assets) can
            legitimately raise when an upstream dependency is merely
            not-yet-WRITTEN under dry-run on a fresh database, and that
            must read as "would seed", not a crash. This is the same
            "skip a downstream step whose upstream id is unknown under
            dry-run" posture the Supply availability step above already
            takes, made explicit here because the dependency is an
            object, not just an id.
            """
            if state is not None:
                report.note("exists", label)
                return state
            if dry_run:
                report.note("seeded", label, "dry-run, not written")
                return None
            events = decide_thunk()
            envelopes = [
                to_new_event(
                    event_type=event_type_name_fn(event),
                    payload=to_payload_fn(event),
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
                    stream_type=stream_type,
                    stream_id=stream_id,
                    expected_version=0,
                    events=envelopes,
                )
            except ConcurrencyError:
                report.note("exists", label, "raced another writer; already present")
                return await reload()
            report.note("seeded", label)
            return await reload()

        capability_id = recipe_seed_id(facility_code, beamline, "capability", "acquisition")
        capability: Capability | None = await seed_genesis(
            stream_type="Capability",
            state=await load_capability(kernel.event_store, capability_id),
            decide_thunk=lambda: decide_capability(
                state=None,
                command=DefineCapability(
                    code="cora.capability.acquisition",
                    name="Acquisition",
                    # A dark/flat baseline capture opens or closes the
                    # station shutter and captures a frame stack; both
                    # are real preconditions of "Acquisition" at 2-BM,
                    # not an arbitrary choice. Covered by the union of
                    # the Shutter + Camera family affordances below.
                    required_affordances=frozenset({Affordance.SHUTTERABLE, Affordance.CAPTURING}),
                    # Only ever bound via Method in this ceremony; no
                    # Procedure realizes this Capability, so PROCEDURE
                    # is left out rather than added speculatively.
                    executor_shapes=frozenset({ExecutorShape.METHOD}),
                ),
                now=clock.now(),
                new_id=capability_id,
            ),
            event_type_name_fn=capability_event_type_name,
            to_payload_fn=capability_to_payload,
            stream_id=capability_id,
            label="capability cora.capability.acquisition",
            reload=lambda: load_capability(kernel.event_store, capability_id),
        )

        # dark_field/flat_field need exactly the two Assets seeded above;
        # no Scintillator or other microscope-family requirement, unlike
        # the broader scenario-test fixtures for these same recipes
        # (this ceremony registers a minimal, real, conductible pair,
        # not the fuller test rig). fly_scan additionally needs the
        # Rotary stage: continuous sample rotation is the defining
        # feature of a real fly-scan, unlike a static baseline capture.
        recipe_family_ids = frozenset({shutter_family_id, family_id})
        recipe_family_ids_with_rotary = recipe_family_ids | {rotary_family_id}

        async def seed_acquisition_recipe(
            method_name: str,
            practice_name: str,
            plan_name: str,
            *,
            include_rotary: bool = False,
        ) -> None:
            needed_family_ids = (
                recipe_family_ids_with_rotary if include_rotary else recipe_family_ids
            )
            method_id = recipe_seed_id(facility_code, beamline, "method", method_name)
            method: Method | None = await seed_genesis(
                stream_type="Method",
                state=await load_method(kernel.event_store, method_id),
                decide_thunk=lambda: decide_method(
                    state=None,
                    command=DefineMethod(
                        name=method_name,
                        capability_id=capability_id,
                        execution_pattern=ExecutionPattern.BATCH,
                        needed_family_ids=needed_family_ids,
                    ),
                    capability=capability,
                    now=clock.now(),
                    new_id=method_id,
                ),
                event_type_name_fn=method_event_type_name,
                to_payload_fn=method_to_payload,
                stream_id=method_id,
                label=f"method {method_name}",
                reload=lambda: load_method(kernel.event_store, method_id),
            )

            practice_id = recipe_seed_id(facility_code, beamline, "practice", practice_name)
            practice: Practice | None = await seed_genesis(
                stream_type="Practice",
                state=await load_practice(kernel.event_store, practice_id),
                decide_thunk=lambda: decide_practice(
                    state=None,
                    command=DefinePractice(
                        name=practice_name,
                        method_id=method_id,
                        # "Site-level Asset this Practice belongs to"
                        # (DefinePractice's own docstring); the root Unit
                        # Asset IS that binding point. No distinct Site
                        # aggregate exists in the codebase.
                        site_id=root_id,
                    ),
                    now=clock.now(),
                    new_id=practice_id,
                ),
                event_type_name_fn=practice_event_type_name,
                to_payload_fn=practice_to_payload,
                stream_id=practice_id,
                label=f"practice {practice_name}",
                reload=lambda: load_practice(kernel.event_store, practice_id),
            )

            plan_id = recipe_seed_id(facility_code, beamline, "plan", plan_name)

            def build_plan_events() -> list[Any]:
                # Only ever called for real (never under dry-run, and
                # never when this Plan already exists), by which point
                # this same ceremony run has already written the
                # Practice/Method/Assets it binds. The asserts are that
                # invariant, not a runtime possibility.
                assert practice is not None
                assert method is not None
                assert shutter is not None
                assert acquisition_camera is not None
                assets = {
                    shutter_id: shutter,
                    acquisition_camera_id: acquisition_camera,
                }
                family_affordances = {
                    shutter_family_id: shutter_family.affordances,
                    family_id: family.affordances,
                }
                if include_rotary:
                    assert rotary_stage is not None
                    assets[rotary_stage_id] = rotary_stage
                    family_affordances[rotary_family_id] = rotary_family.affordances
                context = PlanBindingContext(
                    practice=practice,
                    method=method,
                    assets=assets,
                    capability=capability,
                    family_affordances=family_affordances,
                )
                return decide_plan(
                    state=None,
                    command=DefinePlan(
                        name=plan_name,
                        practice_id=practice_id,
                        asset_ids=frozenset(assets),
                    ),
                    context=context,
                    now=clock.now(),
                    new_id=plan_id,
                )

            plan: Plan | None = await seed_genesis(
                stream_type="Plan",
                state=await load_plan(kernel.event_store, plan_id),
                decide_thunk=build_plan_events,
                event_type_name_fn=plan_event_type_name,
                to_payload_fn=plan_to_payload,
                stream_id=plan_id,
                label=f"plan {plan_name}",
                reload=lambda: load_plan(kernel.event_store, plan_id),
            )
            _ = plan

        async def deprecate_plan_if_present(old_plan_name: str) -> None:
            """One-time migration step, permanent in this file: the Plans
            bound to the pre-2026-08-14 (un-located) Assets are superseded
            by the `_v2` Plans below. No-op when the old Plan never existed
            (fresh deployment) or is already Deprecated (prior run already
            migrated it). Hygiene, not a safety requirement: `start_run`
            already refuses any Plan bound to a Decommissioned Asset
            regardless of this step.
            """
            old_plan_id = recipe_seed_id(facility_code, beamline, "plan", old_plan_name)
            old_plan = await load_plan(kernel.event_store, old_plan_id)
            if old_plan is None:
                return
            if old_plan.status is PlanStatus.DEPRECATED:
                report.note("exists", f"plan {old_plan_name} deprecated")
                return
            if dry_run:
                report.note("seeded", f"plan {old_plan_name} deprecated", "dry-run, not written")
                return
            _, old_plan_version = await kernel.event_store.load("Plan", old_plan_id)
            deprecate_events = decide_deprecate_plan(
                state=old_plan,
                command=DeprecatePlan(plan_id=old_plan_id, reason=DeprecationReason.SUPERSEDED),
                now=clock.now(),
            )
            deprecate_envelopes = [
                to_new_event(
                    event_type=plan_event_type_name(event),
                    payload=plan_to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=ids.new_id(),
                    command_name=_COMMAND_NAME,
                    correlation_id=run_correlation_id,
                    principal_id=SYSTEM_PRINCIPAL_ID,
                )
                for event in deprecate_events
            ]
            await kernel.event_store.append(
                stream_type="Plan",
                stream_id=old_plan_id,
                expected_version=old_plan_version,
                events=deprecate_envelopes,
            )
            report.note("seeded", f"plan {old_plan_name} deprecated")

        await deprecate_plan_if_present("2BM_dark_field_plan")
        await deprecate_plan_if_present("2BM_flat_field_plan")

        await seed_acquisition_recipe(
            "dark_field", "2BM_dark_field_practice", "2BM_dark_field_plan_v2"
        )
        await seed_acquisition_recipe(
            "flat_field", "2BM_flat_field_practice", "2BM_flat_field_plan_v2"
        )
        # The actual 2-BM TomoScan workflow the RunWitness's promotion path
        # (cora.api._run_witness) watches: a fly-scan capture, distinct from
        # the two conductible baseline captures above. Watch-only, not
        # conducted: no operator REST/UI surface ever selects this Plan for
        # start_run, matching record_witnessed_run's own stub route/tool.
        # `_v1`, not `_v2`: there is no prior un-located fly_scan Plan to
        # supersede via deprecate_plan_if_present. include_rotary=True: a
        # real fly-scan's defining feature is continuous sample rotation,
        # unlike the two static baseline captures above.
        await seed_acquisition_recipe(
            "fly_scan",
            "2BM_fly_scan_practice",
            "2BM_fly_scan_plan_v1",
            include_rotary=True,
        )

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
            "Register what a deployment needs before ingest_scan can "
            "record (the beamline root Unit, a camera Device with its "
            "Capturing-bearing family, a Storage supply) and before "
            "start_run has a real plan_id to bind to (a StationShutter "
            "and a second camera Device located in 2-BM-B, plus the "
            "Capability -> Method -> Practice -> Plan chain for the "
            "dark_field / flat_field recipes, bound to those two). "
            "Idempotent; re-runs report and change nothing."
        ),
    )
    parser.add_argument("--facility-code", default="cora")
    parser.add_argument("--beamline", default="2-bm")
    parser.add_argument("--root-name", default="2-BM")
    parser.add_argument("--camera-name", default="Camera")
    parser.add_argument("--camera-family-name", default="Camera")
    parser.add_argument("--supply-name", default="analysis-tier")
    parser.add_argument("--shutter-name", default="StationShutter")
    # Default deliberately distinct from --camera-name's own default
    # ("Camera"): both default to that name would derive the SAME
    # asset_seed_id and collide. Pass --acquisition-camera-name Camera
    # explicitly for a deployment (like 2-BM) where --camera-name
    # already names a different physical camera under an override.
    parser.add_argument("--acquisition-camera-name", default="AcquisitionCamera")
    parser.add_argument("--rotary-stage-name", default="RotaryStage")
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
            shutter_name=args.shutter_name,
            acquisition_camera_name=args.acquisition_camera_name,
            rotary_stage_name=args.rotary_stage_name,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
