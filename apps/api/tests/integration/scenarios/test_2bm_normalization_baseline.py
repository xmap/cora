"""Normalization baseline (darks + flats) at APS 2-BM, CORA-conducted from a Recipe.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Data, Operation, Recipe

Scenario test for the combined dark + flat normalization ceremony,
modeled as a deployment Recipe and run as the first deliberate consumer
of the Procedure Conductor. The ceremony is a Recipe (a templated step
list) realizing the existing `cora.capability.acquisition`; an operator
registers a Procedure from it (`register_procedure_from_recipe`), and the
conduct handler re-expands the recipe into conduct steps and drives them
through the ControlPort against a soft IOC. It composes the two shipped
record-path captures (`dark_baseline` + `flat_baseline`) into one
conducted, modeled ceremony that produces the normalization baseline
every tomographic Run normalizes against (darks are subtracted, flats
divide).

See [[project_flat_dark_prologue_design]] for the design lock and
[[project_resumable_conduct_design]] for the re-establishment-prologue
model this ceremony is the buildable-now first instance of. See
[[project_seam_model]] for why this is a deliberate Actuate-axis move
(CORA conducts), not the record-path the live 2-BM seam uses today.

## Why this scenario exists

A conduct-path "101" that exercises the whole modeled ladder end to end:
Capability -> Recipe (step template) -> Procedure (register-from-recipe)
-> expand -> Conductor -> ControlPort -> soft IOC, with zero
live-hardware risk, before the more complex consumers (fly-scan resume,
autonomous control) ride the same rails.

  1. First scenario that drives the Procedure Conductor, AND the first
     end-to-end exercise of the recipe-driven conduct path (define recipe
     -> register-from-recipe -> conduct re-expands the pinned template).
     Every other 2-BM scenario is record-path (hand-built
     `append_activities` entries, no Conductor).
  2. First use of the `flats` staging action: a save-and-restore capture
     that reads the sample axis, retracts it off the beam by a clearance,
     collects, and restores the axis. It lives in `cora.operation.staging`
     (a composition over `collect`), not among the scan primitives.
  3. First Dataset whose `producing_actuation_kind` is derived from a
     conducted Procedure: the soft IOC is a declared simulator, so the
     conduct observes `Simulated` and that provenance rides through the
     terminal event onto the registered baseline Dataset.

## Domain shape

The DATA need is universal across CT facilities: every pipeline (tomopy,
ASTRA, plain numpy) flat-field corrects raw projections against dark +
flat references. The CONCRETE sequence below follows TomoScan / 2-BM
practice but is staff-confirm-pending per the design lock's open
questions on transit-safety ordering and ceremony ORDER / FREQUENCY:

  1. Close the shutter; acquire N dark frames (detector dark current).
  2. Open the shutter; retract the sample off the beam; acquire N flat
     frames (the beam profile through empty optics); restore the sample.
  3. Close the shutter (return to the safe state).
  4. Store the baseline so future Runs can normalize against it.

The ceremony starts sample-in and ends sample-in (the `flats` body
restores), and ends shutter-closed (matching the `flat_baseline` sibling
and recipes.md return-to-safe). The sample transits the live beam during
both the flat retraction and the restore (the shutter closes only after
the flats step), which follows TomoScan's open-beam practice at 2-BM
(SBS as the per-scan fast shutter); confirm before any live wiring.

## Stand-in PVs (illustrative-pending-staff)

The soft IOC carries generic test PVs, NOT production 2-BM addresses.
This mapping is illustrative and MUST be confirmed with staff before any
live-EPICS wiring:

  - shutter -> `long_value` (0 = closed, 1 = open). The real station
    shutter is a PSS-owned categorical leaf (S02BM-PSS:SBS family) with
    an INVERTED sense; its leaf name and closed-code are unconfirmed and
    safety-load-bearing, so this scenario uses a neutral binary stand-in.
  - sample-out axis -> `double_value` (the SampleTop_X analog). The real
    retract axis, clearance, and any theta-park coupling are unconfirmed.
  - detector -> `cam1` (the areaDetector ADCore PV family).

Frame counts and dwell are illustrative (tiny, to keep the test fast);
real per-campaign values are operator-bound.

## What this scenario surfaces (gap-finding intent)

  - **The ceremony is a modeled Recipe, not an inline step list.** The
    darks-then-flats template lives in a Recipe realizing the acquisition
    Capability; conduct re-expands the pinned template. This is the
    artifact the design lock specified.
  - **The save-and-restore needs a body today.** `flats` brackets a
    collect with an absolute read-then-restore because conduct steps are
    static (no runtime variable binding). Conduct variable binding is the
    designated next design; it would retire the body.
  - **Conducted provenance flows to the artifact.** The Dataset carries
    `producing_actuation_kind="Simulated"` derived from the conduct, the
    fact that gates `promote_dataset` later. A live (non-simulated)
    conduct would carry `Physical` and clear that gate.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections import Counter
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register_dataset
from cora.operation.acquisitions import collect
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import PostgresActivityStore
from cora.operation.conductor import Conductor, InMemoryActionRegistry
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.conduct_procedure import ConductProcedure
from cora.operation.features.conduct_procedure import bind as bind_conduct
from cora.operation.features.register_procedure_from_recipe import RegisterProcedureFromRecipe
from cora.operation.features.register_procedure_from_recipe import bind as bind_register_from_recipe
from cora.operation.features.start_procedure import bind as bind_start
from cora.operation.ports.control_port import ActuationKind
from cora.operation.staging import flats
from cora.recipe.aggregates.recipe import (
    RecipeActionStep,
    RecipeCheckStep,
    RecipeSetpointStep,
)
from cora.recipe.features.define_recipe import DefineRecipe
from cora.recipe.features.define_recipe import bind as bind_define_recipe
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 22, 10, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020e0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020e00aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000020e0c01")

# Illustrative-pending-staff stand-in codes (see module docstring).
_SHUTTER_CLOSED = 0
_SHUTTER_OPEN = 1
_DARK_FRAMES = 3
_FLAT_FRAMES = 3
_DWELL_S = 0.05
_CLEARANCE_MM = 5.0


@pytest.mark.integration
async def test_normalization_baseline_recipe_conducts_darks_and_flats_against_softioc(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Define the ceremony Recipe, register a Procedure from it, conduct it to
    Completed against the soft IOC, then register the baseline Dataset with the
    conduct's Simulated provenance derived onto it."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])

    shutter = f"{softioc}long_value"
    axis = f"{softioc}double_value"
    detector = f"{softioc}cam1"

    # ----- Recipe BC: the acquisition Capability + the ceremony Recipe -----
    #
    # The Recipe realizes the EXISTING cora.capability.acquisition (seeded
    # with both executor shapes; register-from-recipe requires Procedure).
    # The template is all-literal (no BindingRef), so no parameters_schema
    # or operator bindings are needed for this calibration ceremony.
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )
    recipe_id = await bind_define_recipe(deps)(
        DefineRecipe(
            name="2BM_normalization_baseline_recipe",
            capability_id=_CAPABILITY_ID,
            steps=(
                # darks: shutter closed, then collect
                RecipeSetpointStep(address=shutter, value=_SHUTTER_CLOSED, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_CLOSED}
                ),
                RecipeActionStep(
                    name="collect",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "repetitions": _DARK_FRAMES,
                        "dwell": _DWELL_S,
                    },
                ),
                # flats: shutter open, then retract sample, collect, restore
                RecipeSetpointStep(address=shutter, value=_SHUTTER_OPEN, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_OPEN}
                ),
                RecipeActionStep(
                    name="flats",
                    params={
                        "detector": detector,
                        "trigger_mode": "Internal",
                        "axis": axis,
                        "clearance": _CLEARANCE_MM,
                        "repetitions": _FLAT_FRAMES,
                        "dwell": _DWELL_S,
                    },
                ),
                # return to safe: shutter closed
                RecipeSetpointStep(address=shutter, value=_SHUTTER_CLOSED, verify=True),
                RecipeCheckStep(
                    address=shutter, criterion={"kind": "equals", "expected": _SHUTTER_CLOSED}
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register a Procedure from the Recipe (lands Defined) -----
    expander = InMemoryRecipeExpander()
    procedure_id = await bind_register_from_recipe(deps, expansion_port=expander)(
        RegisterProcedureFromRecipe(
            name="2-BM normalization baseline (darks + flats, illustrative campaign)",
            kind="normalization_baseline",
            target_asset_ids=(),
            parent_run_id=None,
            recipe_id=recipe_id,
            bindings={},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Conduct: the handler re-expands the pinned recipe + drives the soft IOC -----
    #
    # The soft IOC is a declared simulator (a real CA speaker that is not
    # real hardware); routing through the registry with is_simulated=True is
    # what makes the conduct observe Simulated.
    port = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register(softioc, port, is_simulated=True)
    step_store = PostgresActivityStore(db_pool)
    conductor = Conductor(
        control_port=registry,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({"collect": collect, "flats": flats}),
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )
    conduct = bind_conduct(deps, conductor=conductor, expansion_port=expander)

    try:
        # Recipe-driven: caller steps are empty; the handler re-expands the
        # pinned template (non-empty caller steps are forbidden here).
        result = await conduct(
            ConductProcedure(procedure_id=procedure_id, steps=()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    finally:
        await registry.aclose()

    # ----- Conduct outcome: all eight steps ran, conduct observed Simulated -----

    assert result.succeeded is True
    assert result.completed_count == 8
    assert result.actuation_kind == ActuationKind.SIMULATED.value

    # ----- Procedure FSM stream: Defined -> Running -> (logbook) -> Completed -----

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    # the recipe-driven genesis pins a template-expansion provenance event
    assert "RecipeExpansionRecorded" in event_types
    assert "ProcedureStarted" in event_types
    assert event_types[-1] == "ProcedureCompleted"

    # ----- Journal: eight logical step entries + five pre-effect markers -----
    #
    # The clock is frozen so all entries share sampled_at; assert on the
    # order-independent multiset AND the clock/id-independent step_index set
    # (closing the kind-preserving-misorder gap). Setpoint + action are
    # side-effecting (one pre-effect in_flight marker each); checks are pure
    # reads (no marker). Eight steps: 3 setpoints (idx 0,3,6), 3 checks
    # (idx 1,4,7), 2 actions (idx 2,5); markers on the 5 side-effecting ones.
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind, payload FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1",
            procedure_id,
        )
    logical = [r for r in rows if r["payload"]["result"] != "in_flight"]
    markers = [r for r in rows if r["payload"]["result"] == "in_flight"]
    assert Counter(r["step_kind"] for r in logical) == {"setpoint": 3, "check": 3, "action": 2}
    assert {r["payload"]["step_index"] for r in logical} == {0, 1, 2, 3, 4, 5, 6, 7}
    assert {r["payload"]["step_index"] for r in markers} == {0, 2, 3, 5, 6}

    # ----- Data BC: the normalization baseline Dataset (terminal-gated) -----
    #
    # producing_procedure_id links the artifact to the conduct and exercises
    # the register_dataset terminal gate (the Procedure is Completed, so it
    # passes). subject_id=None is the calibration idiom (no sample Subject).
    dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_normalization_baseline_2026-06-22",
            uri="file:///data/2bm/2026-06/normalization_baseline.h5",
            checksum_algorithm="sha256",
            checksum_value="a" * 64,
            byte_size=2448 * 2048 * 2 * (_DARK_FRAMES + _FLAT_FRAMES),
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            producing_procedure_id=procedure_id,
            producing_run_id=None,
            subject_id=None,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    dataset_events, _ = await deps.event_store.load("Dataset", dataset_id)
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered"]
    payload = dataset_events[0].payload
    assert payload["producing_procedure_id"] == str(procedure_id)
    assert payload["subject_id"] is None
    # The conduct's Simulated provenance is derived onto the Dataset (the
    # fact promote_dataset gates on).
    assert payload["producing_actuation_kind"] == ActuationKind.SIMULATED.value
