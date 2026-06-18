"""Iterative tomographic reconstruction recorded at APS 2-BM.

cluster: Runs
archetype: cycle
bc_primary: Recipe
bc_touches: Data, Equipment, Recipe, Run, Subject

Scenario test for the RECORD-the-recon compute path: a reconstruction is
a compute Method (ITERATIVE) realizing a no-affordance compute Capability,
bound in a Plan over a ComputeNode Asset, executed as a Run that names its
input (the raw projection Dataset) and its output (the reconstructed
Dataset, lineage-linked via derived_from). Execution stays external; CORA
records the recipe, the node it ran on, the parameters, and the lineage.

See [[project-compute-modeling-stage0-design]] (L2 RECORD-not-CONDUCT, L3
the three Method classification fields, L8 ComputeNode hardware box, L11
the recon Plan binds a ComputeNode Asset).

## Why this scenario exists

Three firsts in CORA's corpus:

  1. First ITERATIVE Method (execution_pattern), with a stopping-key
     parameters_schema (num_iter / tol) satisfying the L4(a) invariant.
  2. First ComputeNode Equipment Family + Asset: an empty-affordance leaf
     (GPU/RAM in settings_schema) that a Plan binds. It is never activated
     (define_plan / start_run gate only on Decommissioned), consistent
     with the MotionController leaf convention.
  3. First non-empty derived_from in the corpus: the reconstructed Dataset
     declares lineage back to the raw projection Dataset.

## Domain shape

Reconstruction turns a stack of raw projections into a 3-D volume. An
iterative solver (SIRT / FISTA) refines the estimate until it converges
(tolerance) or exhausts its iteration budget (num_iter). The recon runs
on a GPU node; CORA records which node, which algorithm, and the
input/output data lineage, without conducting the job itself.

## What this scenario surfaces

  - **The recon Run carries no Subject.** The sample was mounted during
    the original acquisition; the reconstruction operates on data, not the
    physical sample, so the Run uses subject_id=None (the calibration /
    dark-field path that skips the mount-state gate). The Subject lineage
    lives on the Datasets, not the Run.
  - **The ComputeNode is not in an Enclosure.** Compute hardware sits
    outside the beamline radiation enclosures, so start_run's enclosure
    permit gate is permit-by-default (no scoped Asset references an
    Enclosure). The compute node also needs no Supply, so the supply gate
    skips.
  - **Whether a record-only recon Run requires a Clearance (design L9)
    stays an open operator question.** This scenario passes via the
    default AlwaysCoveredClearanceLookup, which does not decide L9.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register_dataset
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.update_asset_settings import UpdateAssetSettings
from cora.equipment.features.update_asset_settings import bind as bind_update_asset_settings
from cora.equipment.features.update_family_settings_schema import UpdateFamilySettingsSchema
from cora.equipment.features.update_family_settings_schema import (
    bind as bind_update_family_settings_schema,
)
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.recipe.features.update_method_parameters_schema import UpdateMethodParametersSchema
from cora.recipe.features.update_method_parameters_schema import bind as bind_update_method_schema
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.register_subject import bind as bind_register_subject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 20, 9, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000c0de1")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000c0de2")
_SITE_ID = UUID("01900000-0000-7000-8000-0000000c0de3")

# Compute Capability (no affordances; Method-shaped executor). Seeded
# directly into the event store, same as every other Capability.
_CAPABILITY_RECON_ID = UUID("01900000-0000-7000-8000-0000000c0dca")

# ComputeNode Family: name-derived stream id (uuid5), like every Family.
_FAMILY_COMPUTE_NODE_ID = family_stream_id(FamilyName("ComputeNode"))


def _recon_schema() -> dict[str, Any]:
    """Parameters_schema for the ITERATIVE recon Method. Declares BOTH a
    budget (num_iter) and a tolerance (tol) stopping key, satisfying the
    L4(a) invariant (one or two; both allowed)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "num_iter": {"type": "integer", "minimum": 1},
            "tol": {"type": "number", "minimum": 0},
        },
    }


def _compute_node_settings_schema() -> dict[str, Any]:
    """ComputeNode.settings_schema: GPU + RAM specs of the box."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "gpu_model": {"type": "string"},
            "gpu_count": {"type": "integer", "minimum": 1},
            "gpu_memory_gb": {"type": "number", "minimum": 1},
            "system_ram_gb": {"type": "number", "minimum": 1},
        },
        "required": ["gpu_model", "gpu_count"],
    }


@pytest.mark.integration
async def test_reconstruction_records_recipe_run_and_lineage(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end RECORD-the-recon: define a ComputeNode Family + Asset and
    an ITERATIVE reconstruction Method/Capability, bind them in a Plan,
    register the raw projection Dataset, run the (record-only) recon Run,
    and register the reconstructed Dataset with derived_from lineage back
    to the raw one. Assert the Method's execution_pattern, the node
    binding, and the Dataset lineage."""
    # Generous fresh id queue; FixedIdGenerator tolerates leftovers and we
    # capture every aggregate id from its handler's return value.
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])

    # ----- Recipe BC: the no-affordance compute Capability -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_RECON_ID,
        code="cora.capability.reconstruction",
        name="Reconstruction",
        shapes=frozenset({ExecutorShape.METHOD}),
    )

    # ----- Equipment BC: ComputeNode Family (empty-affordance leaf) + Asset -----

    await bind_define_family(deps)(
        DefineFamily(name="ComputeNode", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_family_settings_schema(deps)(
        UpdateFamilySettingsSchema(
            family_id=_FAMILY_COMPUTE_NODE_ID,
            settings_schema=_compute_node_settings_schema(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    node_asset_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="gpu-recon-01", tier=AssetTier.DEVICE, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=node_asset_id, family_id=_FAMILY_COMPUTE_NODE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_asset_settings(deps)(
        UpdateAssetSettings(
            asset_id=node_asset_id,
            settings_patch={
                "gpu_model": "NVIDIA A100",
                "gpu_count": 4,
                "gpu_memory_gb": 80.0,
                "system_ram_gb": 512.0,
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # The ComputeNode Asset is NOT activated: an empty-affordance leaf has
    # no command surface for Active to mean anything, and define_plan /
    # start_run gate only on Decommissioned.

    # ----- Recipe BC: ITERATIVE recon Method + schema + Practice + Plan -----

    method_id = await bind_define_method(deps)(
        DefineMethod(
            name="iterative_reconstruction_sirt",
            capability_id=_CAPABILITY_RECON_ID,
            execution_pattern=ExecutionPattern.ITERATIVE,
            needed_family_ids=frozenset({_FAMILY_COMPUTE_NODE_ID}),
            monotone_quality=True,
            resumable_from_checkpoint=True,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_method_schema(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=_recon_schema()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_iterative_reconstruction_practice",
            method_id=method_id,
            site_id=_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_iterative_reconstruction_plan",
            practice_id=practice_id,
            asset_ids=frozenset({node_asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Subject + raw projection Dataset (the recon input) -----

    subject_id = await bind_register_subject(deps)(
        RegisterSubject(name="iron-bearing sandstone core (recon study)"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    raw_dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_proj_2026-05-20_raw",
            uri="file:///data/2bm/2026-05/proj_raw.h5",
            checksum_algorithm="sha256",
            checksum_value="a" * 64,
            byte_size=24_000_000_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
            producing_run_id=None,
            subject_id=subject_id,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Run BC: the record-only reconstruction Run -----

    run_id = await bind_start_run(deps)(
        StartRun(
            name="SIRT reconstruction of Proposal 2026-1241 sandstone core",
            plan_id=plan_id,
            subject_id=None,
            override_parameters={"num_iter": 200, "tol": 0.0005},
            trigger_source="operator-manual; offline reconstruction on gpu-recon-01",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete_run(deps)(
        CompleteRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Data BC: the reconstructed Dataset, lineage-linked to the raw -----

    recon_dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_recon_2026-05-20_sirt",
            uri="file:///data/2bm/2026-05/recon_sirt.h5",
            checksum_algorithm="sha256",
            checksum_value="b" * 64,
            byte_size=96_000_000_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomoproc"}),
            producing_run_id=run_id,
            subject_id=subject_id,
            derived_from=frozenset({raw_dataset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: the Method recorded the ITERATIVE classification -----

    method_events, _ = await deps.event_store.load("Method", method_id)
    defined = next(e for e in method_events if e.event_type == "MethodDefined")
    assert defined.payload["execution_pattern"] == "Iterative"
    assert defined.payload["monotone_quality"] is True
    assert defined.payload["resumable_from_checkpoint"] is True
    # The L4(a)-gated stopping-key schema actually landed (num_iter + tol).
    schema_updated = next(
        e for e in method_events if e.event_type == "MethodParametersSchemaUpdated"
    )
    assert set(schema_updated.payload["parameters_schema"]["properties"]) >= {"num_iter", "tol"}

    # ----- Assert: ComputeNode Family is an empty-affordance leaf -----

    family_events, _ = await deps.event_store.load("Family", _FAMILY_COMPUTE_NODE_ID)
    family_defined = next(e for e in family_events if e.event_type == "FamilyDefined")
    assert family_defined.payload["affordances"] == []

    # ----- Assert: the node Asset carries the ComputeNode Family + GPU settings -----

    asset_events, _ = await deps.event_store.load("Asset", node_asset_id)
    asset_event_types = [e.event_type for e in asset_events]
    assert asset_event_types == ["AssetRegistered", "AssetFamilyAdded", "AssetSettingsUpdated"]
    assert "AssetActivated" not in asset_event_types
    # The schema-validated GPU/RAM settings actually persisted on the node.
    settings_updated = next(e for e in asset_events if e.event_type == "AssetSettingsUpdated")
    assert settings_updated.payload["settings"]["gpu_model"] == "NVIDIA A100"
    assert settings_updated.payload["settings"]["gpu_count"] == 4

    # ----- Assert: the recon Run completed and carried no Subject -----

    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]
    # Central modeling claim: a record-only recon Run mounts no sample.
    assert run_events[0].payload["subject_id"] is None

    # ----- Assert: the reconstructed Dataset declares lineage to the raw one -----

    recon_events, recon_version = await deps.event_store.load("Dataset", recon_dataset_id)
    assert recon_version == 1
    recon_payload = recon_events[0].payload
    assert recon_payload["derived_from"] == [str(raw_dataset_id)]
    assert UUID(recon_payload["producing_run_id"]) == run_id
    assert UUID(recon_payload["subject_id"]) == subject_id
