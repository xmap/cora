"""Shared tomography-imaging-chain helpers for 2-BM-shape scenario tests.

Extracted by the scenarios-surface migration (Step 5 of the May 2026
refactor pass) after 14 scenarios under the Runs + Advisories +
Staging clusters were all duplicating the same install + activate +
recipe-ladder ceremony for the canonical four-device imaging chain.

## Three coupled helpers

`install_and_activate_tomography_assets()` bundles the
`_facility_fixture.install_aps_unit()` call with the four
`activate_asset` calls that immediately follow it in every tomography
scenario; `tomography_install_id_prefix()` returns the matching
`FixedIdGenerator` queue prefix. The pattern matches
`_facility_fixture` and `_beamtime_fixture`: helpers must be used as
a pair, prefix at the right slot in the id queue, drift corrupts
every downstream allocation.

`define_recipe_ladder()` and `recipe_ladder_id_prefix()` are the
Recipe-BC half: one parameterized factory that runs
`define_method` + optional `update_method_parameters_schema` +
`define_practice` + `define_plan` for any caller-supplied spec. The
factory is the right abstraction because the `define_method` call
itself is the thing tested in many scenarios (operator declares the
Recipe ladder mid-test); pre-baked Methods would erase that surface.

## Why hard-code the four canonical Devices

The Aerotech rotary + SampleTop_X linear stage + Oryx 5MP camera +
LuAG scintillator are the standard 2-BM micro-CT imaging chain. Every
tomography-flavour scenario uses exactly these four, with the same
Device names and the same Family kinds. Hard-coding the names +
Family kinds in the fixture removes a per-scenario boilerplate
loop and one whole layer of plumbing constants from the caller. The
caller still supplies the UUIDs (mnemonic-hex tags per scenario,
matching the `_facility_fixture` convention).

Alignment scenarios use a different mix of Devices (per-routine tilt
stages, focus motors, etc.) and are NOT a fit for this fixture;
extracting an alignment-specific fixture is deferred. The fixture
is deliberately not generalised across asset
shapes today.

## Usage shape

```python
_TOMO_ASSETS = TomographyAssetIds(
    unit_id=_UNIT_ID,
    rotary_cap_id=_CAP_ROTARY_ID, linear_x_cap_id=_CAP_LINEAR_ID,
    camera_cap_id=_CAP_CAMERA_ID, scintillator_cap_id=_CAP_SCIN_ID,
    rotary_id=_ASSET_ROTARY_ID, linear_x_id=_ASSET_LINEAR_ID,
    camera_id=_ASSET_CAMERA_ID, scintillator_id=_ASSET_SCIN_ID,
)
_RECIPE = RecipeSpec(
    method_id=_METHOD_ID,
    method_name="tomography",
    needed_family_ids=frozenset({_CAP_ROTARY_ID, _CAP_LINEAR_ID, _CAP_CAMERA_ID, _CAP_SCIN_ID}),
    parameters_schema={...},
    practice_id=_PRACTICE_ID,
    practice_name="2BM_tomography_practice",
    site_id=_APS_ID,
    plan_id=_PLAN_ID,
    plan_name="2BM_porous_media_plan",
    plan_asset_ids=frozenset(
        {_ASSET_ROTARY_ID, _ASSET_LINEAR_ID, _ASSET_CAMERA_ID, _ASSET_SCIN_ID}
    ),
)

def _id_queue() -> list[UUID]:
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject event
        *recipe_ladder_id_prefix(spec=_RECIPE),
        # ... scenario-specific ids follow
    ]

async def test_...(db_pool):
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    await install_and_activate_tomography_assets(
        deps, principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID, asset_ids=_TOMO_ASSETS,
    )
    await open_beamtime(deps, ...)
    await bind_mount_subject(deps)(...)
    await define_recipe_ladder(deps, principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID, spec=_RECIPE)
    # ... scenario-specific commands follow
```
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from cora.access.aggregates.actor import ProfileStore
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.infrastructure.kernel import Kernel
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.recipe.features.update_method_parameters_schema import UpdateMethodParametersSchema
from cora.recipe.features.update_method_parameters_schema import (
    bind as bind_update_method_schema,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    FacilityIds,
    facility_id_prefix,
    install_aps_unit,
)

# Canonical 2-BM micro-CT imaging chain. Names + Family kinds are
# fixture-owned because they describe the physical apparatus, not the
# scenario; UUIDs remain scenario-supplied per the audit-trail convention.
ROTARY_NAME = "Rotary"
LINEAR_X_NAME = "SampleTop_X"
CAMERA_NAME = "Camera"
SCINTILLATOR_NAME = "Scintillator"

ROTARY_CAP_NAME = "RotaryStage"
LINEAR_X_CAP_NAME = "LinearStage"
CAMERA_CAP_NAME = "Camera"
SCINTILLATOR_CAP_NAME = "Scintillator"


@dataclass(frozen=True)
class TomographyAssetIds:
    """Scenario-supplied UUIDs for the canonical 4-Device tomography chain
    plus the root beamline Unit that hosts them."""

    unit_id: UUID
    rotary_cap_id: UUID
    linear_x_cap_id: UUID
    camera_cap_id: UUID
    scintillator_cap_id: UUID
    rotary_id: UUID
    linear_x_id: UUID
    camera_id: UUID
    scintillator_id: UUID


def _tomography_devices(ids: TomographyAssetIds) -> tuple[DeviceSpec, ...]:
    return (
        DeviceSpec(ROTARY_NAME, ids.rotary_id, ROTARY_CAP_NAME, ids.rotary_cap_id),
        DeviceSpec(LINEAR_X_NAME, ids.linear_x_id, LINEAR_X_CAP_NAME, ids.linear_x_cap_id),
        DeviceSpec(CAMERA_NAME, ids.camera_id, CAMERA_CAP_NAME, ids.camera_cap_id),
        DeviceSpec(
            SCINTILLATOR_NAME,
            ids.scintillator_id,
            SCINTILLATOR_CAP_NAME,
            ids.scintillator_cap_id,
        ),
    )


def tomography_install_id_prefix(*, asset_ids: TomographyAssetIds) -> list[UUID]:
    """FixedIdGenerator queue prefix for `install_and_activate_tomography_assets()`.

    Combines `facility_id_prefix()` for the install + 4 anonymous event
    ids for the per-Device `activate_asset` calls that follow.
    """
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=asset_ids.unit_id,
            devices=_tomography_devices(asset_ids),
        ),
        # 4 activate_asset event ids (rotary, linear_x, camera, scintillator)
        e(),
        e(),
        e(),
        e(),
    ]


async def install_and_activate_tomography_assets(
    deps: Kernel,
    *,
    profile_store: ProfileStore,
    principal_id: UUID,
    correlation_id: UUID,
    asset_ids: TomographyAssetIds,
) -> FacilityIds:
    """Install the 2-BM Unit with the 4-Device tomography chain, then
    activate each Device. Returns the FacilityIds for caller reference.

    Activation order matches `tomography_install_id_prefix()` exactly:
    rotary, linear_x, camera, scintillator.
    """
    facility_ids = await install_aps_unit(
        deps,
        profile_store=profile_store,
        correlation_id=correlation_id,
        unit_id=asset_ids.unit_id,
        devices=_tomography_devices(asset_ids),
        unit_name="2-BM",
    )
    for aid in (
        asset_ids.rotary_id,
        asset_ids.linear_x_id,
        asset_ids.camera_id,
        asset_ids.scintillator_id,
    ):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=aid),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
    return facility_ids


@dataclass(frozen=True)
class RecipeSpec:
    """Caller-supplied recipe ladder spec: Method + (optional schema)
    + Practice + Plan, all in one factory call.

    `parameters_schema=None` skips the `update_method_parameters_schema`
    call; pass a dict to include it. The fixture parameter must be set
    consistently with the id-queue prefix produced by
    `recipe_ladder_id_prefix()`.

    `capability_id` is REQUIRED on every Method. The
    `define_recipe_ladder` factory seeds the Capability stream before
    calling `define_method` (via `seed_capability_postgres`-style direct
    event-store append using uuid4 for the event_id, so the
    FixedIdGenerator queue stays untouched). Tests pass any UUID;
    the fixture handles the seeding."""

    method_id: UUID
    method_name: str
    needed_family_ids: frozenset[UUID]
    practice_id: UUID
    practice_name: str
    site_id: UUID
    plan_id: UUID
    plan_name: str
    plan_asset_ids: frozenset[UUID]
    capability_id: UUID
    capability_code: str
    capability_name: str
    parameters_schema: dict[str, Any] | None = None


def recipe_ladder_id_prefix(*, spec: RecipeSpec) -> list[UUID]:
    """FixedIdGenerator queue prefix for `define_recipe_ladder()`.

    Order:
      1. define_method: method_id, event
      2. update_method_parameters_schema (only if spec.parameters_schema): event
      3. define_practice: practice_id, event
      4. define_plan: plan_id, event

    Length = 6 without schema, 7 with schema."""
    e = uuid4
    ids: list[UUID] = [spec.method_id, e()]
    if spec.parameters_schema is not None:
        ids.append(e())
    ids.extend([spec.practice_id, e(), spec.plan_id, e()])
    return ids


async def define_recipe_ladder(
    deps: Kernel,
    *,
    principal_id: UUID,
    correlation_id: UUID,
    spec: RecipeSpec,
) -> None:
    """Execute the Method + Practice + Plan recipe-ladder ceremony.

    Calls `define_method`, optionally `update_method_parameters_schema`
    (when `spec.parameters_schema` is set), then `define_practice` and
    `define_plan`. Order matches `recipe_ladder_id_prefix()` exactly.

    Seeds the bound Capability stream before
    `define_method` so the cross-BC `load_capability` succeeds. Uses
    the event-store API directly (uuid4 for the event_id) so the
    FixedIdGenerator queue stays untouched and id-prefix ordering
    remains stable."""
    from tests.integration._helpers import seed_capability_postgres

    await seed_capability_postgres(
        deps.event_store,
        spec.capability_id,
        code=spec.capability_code,
        name=spec.capability_name,
    )
    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name=spec.method_name,
            capability_id=spec.capability_id,
            needed_family_ids=spec.needed_family_ids,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    if spec.parameters_schema is not None:
        await bind_update_method_schema(deps)(
            UpdateMethodParametersSchema(
                method_id=spec.method_id,
                parameters_schema=spec.parameters_schema,
            ),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
    await bind_define_practice(deps)(
        DefinePractice(
            name=spec.practice_name,
            method_id=spec.method_id,
            site_id=spec.site_id,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name=spec.plan_name,
            practice_id=spec.practice_id,
            asset_ids=spec.plan_asset_ids,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )


__all__ = [
    "CAMERA_CAP_NAME",
    "CAMERA_NAME",
    "LINEAR_X_CAP_NAME",
    "LINEAR_X_NAME",
    "ROTARY_CAP_NAME",
    "ROTARY_NAME",
    "SCINTILLATOR_CAP_NAME",
    "SCINTILLATOR_NAME",
    "RecipeSpec",
    "TomographyAssetIds",
    "define_recipe_ladder",
    "install_and_activate_tomography_assets",
    "recipe_ladder_id_prefix",
    "tomography_install_id_prefix",
]
