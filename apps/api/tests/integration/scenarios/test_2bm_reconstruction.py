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

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._reckoner import Reckoner
from cora.api._run_phase_conduct import conduct_phase_then_complete_run
from cora.data.aggregates.dataset import DatasetCannotPromoteError
from cora.data.features.promote_dataset import PromoteDataset
from cora.data.features.promote_dataset import bind as bind_promote_dataset
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
from cora.operation.adapters._tree_hash import sha256_tree
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.adapters.local_process_compute_port import LocalProcessComputePort
from cora.operation.aggregates.procedure import PostgresActivityStore
from cora.operation.conductor import ComputeStep, Conductor, InMemoryActionRegistry
from cora.operation.features.abort_procedure import bind as bind_abort_procedure
from cora.operation.features.append_activities import bind as bind_append_activities
from cora.operation.features.complete_procedure import bind as bind_complete_procedure
from cora.operation.features.conduct_procedure import bind as bind_conduct_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_procedure import bind as bind_start_procedure
from cora.operation.ports.compute_port import JobSpec
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    LaunchArg,
    LaunchSpec,
    build_argv,
    load_method,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.recipe.features.update_method_launch_spec import UpdateMethodLaunchSpec
from cora.recipe.features.update_method_launch_spec import bind as bind_update_method_launch_spec
from cora.recipe.features.update_method_parameters_schema import UpdateMethodParametersSchema
from cora.recipe.features.update_method_parameters_schema import bind as bind_update_method_schema
from cora.run.aggregates.run import load_run
from cora.run.features.abort_run import bind as bind_abort_run
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


@dataclass(frozen=True)
class _ReconFixture:
    """Ids produced by `_seed_recon_recipe`, shared by the RECORD and
    CONDUCT scenarios."""

    method_id: UUID
    plan_id: UUID
    subject_id: UUID
    raw_dataset_id: UUID
    node_asset_id: UUID


async def _seed_recon_recipe(deps: Any) -> _ReconFixture:
    """Seed the shared recon recipe: the no-affordance compute Capability,
    the ComputeNode Family + Asset, the ITERATIVE Method + schema +
    Practice + Plan, the Subject, and the raw projection Dataset. Stops
    before start_run so each scenario drives its own Run lifecycle."""
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_RECON_ID,
        code="cora.capability.reconstruction",
        name="Reconstruction",
        shapes=frozenset({ExecutorShape.METHOD}),
    )

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
    return _ReconFixture(
        method_id=method_id,
        plan_id=plan_id,
        subject_id=subject_id,
        raw_dataset_id=raw_dataset_id,
        node_asset_id=node_asset_id,
    )


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
    fixture = await _seed_recon_recipe(deps)
    method_id = fixture.method_id
    node_asset_id = fixture.node_asset_id
    subject_id = fixture.subject_id
    raw_dataset_id = fixture.raw_dataset_id

    # ----- Run BC: the record-only reconstruction Run -----

    run_id = await bind_start_run(deps)(
        StartRun(
            name="SIRT reconstruction of Proposal 2026-1241 sandstone core",
            plan_id=fixture.plan_id,
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
    # A record-only Run was never conducted, so no actuation kind taints it.
    assert recon_payload["producing_actuation_kind"] is None


@pytest.mark.integration
async def test_reconstruction_conducts_via_reckoner_and_gates_promotion(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end CONDUCT-the-recon: the Reckoner submits the recon
    job to a (Simulated) ComputePort, awaits its terminal state, and
    completes the Run carrying the observed actuation kind. The recon
    Dataset registered against that conducted Run inherits
    producing_actuation_kind = Simulated, so the simulator-origin gate
    bars its promotion to Production even after its inputs are promoted."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])
    fixture = await _seed_recon_recipe(deps)

    run_id = await bind_start_run(deps)(
        StartRun(
            name="SIRT reconstruction (conducted) of Proposal 2026-1241",
            plan_id=fixture.plan_id,
            subject_id=None,
            override_parameters={"num_iter": 200, "tol": 0.0005},
            trigger_source="compute-runtime; in-memory executor",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # The Reckoner drives submit -> await -> complete via the
    # in-memory (Simulated) ComputePort. The default seed is Succeeded
    # with an artifact synthesised from the job spec's output_uri.
    runtime = Reckoner(
        compute_port=InMemoryComputePort(),
        complete_run=bind_complete_run(deps),
        abort_run=bind_abort_run(deps),
    )
    result = await runtime.conduct(
        run_id=run_id,
        job_spec=JobSpec(
            command=("tomopy", "recon", "--algorithm", "sirt"),
            input_uris=("file:///data/2bm/2026-05/proj_raw.h5",),
            output_uri="file:///data/2bm/2026-05/recon_sirt.h5",
            parameters={"num_iter": 200, "tol": 0.0005},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result.succeeded
    assert result.artifact_ref is not None

    # ----- Assert: the conduct completed the Run carrying provenance -----

    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]
    completed = run_events[1].payload
    assert completed["actuation_kind"] == "Simulated"
    assert completed["producing_job_id"] is not None
    assert completed["artifact_uri"] == "file:///data/2bm/2026-05/recon_sirt.h5"

    # ----- Data BC: the reconstructed Dataset off the conducted Run -----

    recon_dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_recon_2026-05-20_sirt_conducted",
            uri=result.artifact_ref.uri,
            checksum_algorithm=result.artifact_ref.checksum_algorithm,
            checksum_value=result.artifact_ref.checksum_value,
            byte_size=96_000_000_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomoproc"}),
            producing_run_id=run_id,
            subject_id=fixture.subject_id,
            derived_from=frozenset({fixture.raw_dataset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Central claim: the actuation kind flowed conducted-Run -> Dataset.
    recon_events, _ = await deps.event_store.load("Dataset", recon_dataset_id)
    assert recon_events[0].payload["producing_actuation_kind"] == "Simulated"
    assert recon_events[0].payload["derived_from"] == [str(fixture.raw_dataset_id)]

    # Promote the raw input so the lineage-must-be-Production guard passes;
    # the raw Dataset is an external upload (no producing conduct), so its
    # actuation kind is None and the simulator gate does not bar it.
    await bind_promote_dataset(deps)(
        PromoteDataset(dataset_id=fixture.raw_dataset_id, reason="raw projections peer-reviewed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: simulator-origin recon cannot be promoted to Production -----

    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        await bind_promote_dataset(deps)(
            PromoteDataset(
                dataset_id=recon_dataset_id,
                reason="attempt to promote rehearsal recon",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # It is specifically the simulator-origin gate that blocks it (not the
    # lineage guard, which now passes): the message names the actuation.
    assert "actuation" in str(exc_info.value)


@pytest.mark.integration
async def test_reconstruction_conducts_on_a_real_subprocess_and_is_promotable(
    db_pool: asyncpg.Pool,
    tmp_path: Path,
) -> None:
    """End-to-end CONDUCT on the real local-process executor: the
    Reckoner runs an actual subprocess that writes the recon output,
    captures Physical actuation, and the resulting Dataset (lineage-linked
    and with its raw input promoted) IS promotable to Production. The
    Physical counterpart of the Simulated gate test."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])
    fixture = await _seed_recon_recipe(deps)

    run_id = await bind_start_run(deps)(
        StartRun(
            name="SIRT reconstruction (local subprocess) of Proposal 2026-1241",
            plan_id=fixture.plan_id,
            subject_id=None,
            override_parameters={"num_iter": 200, "tol": 0.0005},
            trigger_source="compute-runtime; local-process executor",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # A real subprocess writes the recon output file, so the artifact's
    # checksum + size are genuine (not synthesised). LocalProcessComputePort
    # declares Physical actuation, so the output is promotable.
    output_path = tmp_path / "recon_sirt.h5"
    runtime = Reckoner(
        compute_port=LocalProcessComputePort(),
        complete_run=bind_complete_run(deps),
        abort_run=bind_abort_run(deps),
    )
    result = await runtime.conduct(
        run_id=run_id,
        job_spec=JobSpec(
            command=(
                sys.executable,
                "-c",
                f"import pathlib; pathlib.Path({str(output_path)!r}).write_bytes(b'recon-volume')",
            ),
            output_uri=output_path.as_uri(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result.succeeded
    assert result.artifact_ref is not None

    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]
    assert run_events[1].payload["actuation_kind"] == "Physical"

    recon_dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_recon_2026-05-20_sirt_physical",
            uri=result.artifact_ref.uri,
            checksum_algorithm=result.artifact_ref.checksum_algorithm,
            checksum_value=result.artifact_ref.checksum_value,
            byte_size=result.artifact_ref.byte_size,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomoproc"}),
            producing_run_id=run_id,
            subject_id=fixture.subject_id,
            derived_from=frozenset({fixture.raw_dataset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    recon_events, _ = await deps.event_store.load("Dataset", recon_dataset_id)
    assert recon_events[0].payload["producing_actuation_kind"] == "Physical"

    # Promote the raw input, then the Physical recon promotes cleanly:
    # no simulator taint, lineage now Production, producing Run Completed.
    await bind_promote_dataset(deps)(
        PromoteDataset(dataset_id=fixture.raw_dataset_id, reason="raw projections peer-reviewed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_promote_dataset(deps)(
        PromoteDataset(dataset_id=recon_dataset_id, reason="recon passed peer review"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    promoted_events, _ = await deps.event_store.load("Dataset", recon_dataset_id)
    assert "DatasetPromoted" in [e.event_type for e in promoted_events]


@pytest.mark.integration
async def test_reconstruction_conducts_directory_output_and_records_tree_hash(
    db_pool: asyncpg.Pool,
    tmp_path: Path,
) -> None:
    """End-to-end CONDUCT of a DIRECTORY output: a real subprocess writes a
    tomopy-style per-slice TIFF stack into a `{stem}_rec/` directory, the
    Reckoner conducts it without aborting (the pre-tree-hash behavior
    raised ArtifactNotFoundError on any non-file output), and the artifact
    carries a deterministic `sha256-tree` digest + summed byte_size + file
    count. The reconstructed Dataset registers with that tree checksum 1:1.

    The Distribution algorithm-equality guard and the attestation-of-tree
    refusal are covered at the decider tier in tests/unit/data; this
    scenario proves the producer + Run + Dataset legs end to end.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])
    fixture = await _seed_recon_recipe(deps)

    run_id = await bind_start_run(deps)(
        StartRun(
            name="SIRT reconstruction (tiff stack) of Proposal 2026-1241",
            plan_id=fixture.plan_id,
            subject_id=None,
            override_parameters={"num_iter": 200, "tol": 0.0005},
            trigger_source="compute-runtime; local-process executor, tiff-stack output",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # A real subprocess writes a directory of per-slice TIFFs (tomopy's
    # default save-format=tiff), so fetch_artifact_ref folds the tree.
    output_dir = tmp_path / "recon_sirt_rec"
    runtime = Reckoner(
        compute_port=LocalProcessComputePort(),
        complete_run=bind_complete_run(deps),
        abort_run=bind_abort_run(deps),
    )
    result = await runtime.conduct(
        run_id=run_id,
        job_spec=JobSpec(
            command=(
                sys.executable,
                "-c",
                (
                    "import pathlib; "
                    f"d = pathlib.Path({str(output_dir)!r}); d.mkdir(parents=True); "
                    "[(d / f'slice_{i:04d}.tif').write_bytes(b'slice-%d' % i) for i in range(8)]"
                ),
            ),
            output_uri=output_dir.as_uri(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result.succeeded
    assert result.artifact_ref is not None

    # The artifact is a directory tree-hash, matching a fresh recompute.
    expected_digest, expected_size, expected_count = sha256_tree(output_dir)
    assert result.artifact_ref.checksum_algorithm == "sha256-tree"
    assert result.artifact_ref.checksum_value == expected_digest
    assert result.artifact_ref.byte_size == expected_size
    assert result.artifact_ref.entry_count == expected_count == 8

    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]
    assert run_events[1].payload["actuation_kind"] == "Physical"

    # The reconstructed Dataset records the tree checksum verbatim.
    recon_dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_recon_2026-05-20_sirt_tiff_stack",
            uri=result.artifact_ref.uri,
            checksum_algorithm=result.artifact_ref.checksum_algorithm,
            checksum_value=result.artifact_ref.checksum_value,
            byte_size=result.artifact_ref.byte_size,
            media_type="image/tiff",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomoproc"}),
            producing_run_id=run_id,
            subject_id=fixture.subject_id,
            derived_from=frozenset({fixture.raw_dataset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    recon_events, _ = await deps.event_store.load("Dataset", recon_dataset_id)
    assert recon_events[0].payload["checksum"]["algorithm"] == "sha256-tree"
    assert recon_events[0].payload["checksum"]["value"] == expected_digest
    assert recon_events[0].payload["producing_actuation_kind"] == "Physical"


def _sirt_launch_spec() -> LaunchSpec:
    """The vetted 2-BM SIRT recon recipe. The algorithm is FIXED in the
    recipe's base_command; the operator-tunable knobs (num_iter, tol) are
    LaunchArgs naming parameters_schema keys, so a Run supplies values,
    never argv tokens."""
    return LaunchSpec(
        base_command=("tomopy", "recon", "--algorithm", "sirt"),
        args=(
            LaunchArg(name="num_iter", flag="--num-iter", required=True),
            LaunchArg(name="tol", flag="--tol", required=True),
        ),
        input_arg="--input",
        output_arg="--output",
    )


@pytest.mark.integration
async def test_reconstruction_conducts_from_vetted_launch_spec(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end CONDUCT from a vetted launch_spec: the recon Method carries
    a SIRT launch_spec; the server derives the argv from that recipe plus the
    Run's effective_parameters (no caller-supplied command), and the
    Reckoner conducts it to a completed, Simulated-provenance Run.

    This is the injection-safe path the conduct endpoint takes for a
    launch_spec Method: a parameter value (num_iter=200) is rendered as
    exactly one argv token, never re-parsed."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])
    fixture = await _seed_recon_recipe(deps)

    # Attach the vetted SIRT recipe to the (schema-bearing) recon Method.
    await bind_update_method_launch_spec(deps)(
        UpdateMethodLaunchSpec(method_id=fixture.method_id, launch_spec=_sirt_launch_spec()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    run_id = await bind_start_run(deps)(
        StartRun(
            name="SIRT reconstruction (vetted launch_spec) of Proposal 2026-1241",
            plan_id=fixture.plan_id,
            subject_id=None,
            override_parameters={"num_iter": 200, "tol": 0.0005},
            trigger_source="compute-runtime; argv built server-side from launch_spec",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Derive the argv the way the conduct endpoint does -----

    method = await load_method(deps.event_store, fixture.method_id)
    assert method is not None
    assert method.launch_spec is not None
    run = await load_run(deps.event_store, run_id)
    assert run is not None

    raw_uri = "file:///data/2bm/2026-05/proj_raw.h5"
    recon_uri = "file:///data/2bm/2026-05/recon_sirt.h5"
    argv = build_argv(
        method.launch_spec,
        run.effective_parameters,
        input_uris=(raw_uri,),
        output_uri=recon_uri,
    )
    # The recipe + validated params render to a deterministic, shell-free argv.
    assert argv == (
        "tomopy",
        "recon",
        "--algorithm",
        "sirt",
        "--num-iter",
        "200",
        "--tol",
        "0.0005",
        "--input",
        raw_uri,
        "--output",
        recon_uri,
    )

    # ----- Conduct the derived job via the (Simulated) ComputePort -----

    runtime = Reckoner(
        compute_port=InMemoryComputePort(),
        complete_run=bind_complete_run(deps),
        abort_run=bind_abort_run(deps),
    )
    result = await runtime.conduct(
        run_id=run_id,
        job_spec=JobSpec(
            command=argv,
            input_uris=(raw_uri,),
            output_uri=recon_uri,
            parameters=dict(run.effective_parameters),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result.succeeded
    assert result.artifact_ref is not None
    assert result.artifact_ref.uri == recon_uri

    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]
    assert run_events[1].payload["actuation_kind"] == "Simulated"


def _recon_conductor(deps: Any, compute_port: Any) -> Conductor:
    """A Conductor wired with the lifecycle handlers + a ComputePort.

    The merged-engine recon path needs the FSM-transition handlers
    (start/complete/abort) so `conduct_procedure` can drive the phase
    Procedure end to end, plus the shared `compute_port` the ComputeStep
    submits its job to. The action registry is empty (a recon phase is
    pure compute, no acquisition action body)."""
    return Conductor(
        control_port=InMemoryControlPort(),
        append_step=bind_append_activities(deps, step_store=PostgresActivityStore(deps.pool)),
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({}),
        compute_port=compute_port,
        start_procedure=bind_start_procedure(deps),
        complete_procedure=bind_complete_procedure(deps),
        abort_procedure=bind_abort_procedure(deps),
    )


@pytest.mark.integration
async def test_reconstruction_conducts_single_stage_phase_via_merged_engine(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end CONDUCT through the MERGED engine: a single-stage compute Run
    whose phase is a one-element [ComputeStep reconstruct] Procedure
    (parent_run_id -> Run). The Conductor walks the file-arm ComputeStep
    (output_uri set -> fetch_artifact_ref), the conduct_phase_then_complete_run
    glue completes the parent Run carrying the folded Simulated kind, and the
    reconstructed volume Dataset registers against producing_run_id with the
    surfaced ArtifactRef. Parity with the single-job Reckoner baseline: the Run
    stays Running across the phase, then RunStarted -> RunCompleted, and the
    Simulated provenance bars promotion (Simulated-blocks).

    This is the floor's proof that the Reckoner class dissolved into one
    step-walking engine: the same recon, conducted as a Procedure PHASE of the
    Run rather than a bespoke compute runtime."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(80)])
    fixture = await _seed_recon_recipe(deps)

    # ----- the parent compute Run (subject-less, like the baseline) -----
    run_id = await bind_start_run(deps)(
        StartRun(
            name="SIRT reconstruction (single-stage merged-engine phase)",
            plan_id=fixture.plan_id,
            subject_id=None,
            override_parameters={"num_iter": 200, "tol": 0.0005},
            trigger_source="compute-runtime; merged engine, single-stage compute phase",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # INVARIANT: the Run is Running after start_run, and STAYS Running across
    # the phase (no new Run FSM state); the glue completes it afterward.
    run = await load_run(deps.event_store, run_id)
    assert run is not None
    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted"]

    # ----- the compute Procedure phase (parent_run_id -> Run), one ComputeStep -----
    procedure_id = await bind_register_procedure(deps)(
        RegisterProcedure(
            name="SIRT reconstruct (compute phase of the recon Run)",
            # noun-LAST (R6), subject-qualified like the operation-noun family
            # (pixel_size_characterization, slit_centering): the volume is the
            # subject, reconstruction the operation.
            kind="volume_reconstruction",
            target_asset_ids=frozenset(),
            parent_run_id=run_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    recon_uri = "file:///data/2bm/2026-05/recon_sirt_merged.h5"
    # output_uri is SET -> the file arm: fetch_artifact_ref, surface ArtifactRef.
    reconstruct = ComputeStep(
        command=("tomopy", "recon", "--algorithm", "sirt"),
        input_uris=("file:///data/2bm/2026-05/proj_raw.h5",),
        output_uri=recon_uri,
        parameters={"num_iter": 200, "tol": 0.0005},
    )

    # ----- conduct the phase via the merged engine, then complete the parent Run -----
    conductor = _recon_conductor(deps, InMemoryComputePort())
    conduct = bind_conduct_procedure(
        deps, conductor=conductor, expansion_port=InMemoryRecipeExpander()
    )
    result = await conduct_phase_then_complete_run(
        run_id=run_id,
        procedure_id=procedure_id,
        conduct_procedure=conduct,
        complete_run=bind_complete_run(deps),
        abort_run=bind_abort_run(deps),
        steps=(reconstruct,),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- the conduct walked the one ComputeStep + folded the Simulated kind -----
    assert result.succeeded is True
    assert result.completed_count == 1
    assert result.actuation_kind == "Simulated"
    # The file arm surfaced the ArtifactRef out of the conducted phase.
    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.uri == recon_uri

    # ----- the phase Procedure ran start -> ComputeStep -> complete -----
    proc_events, _ = await deps.event_store.load("Procedure", procedure_id)
    proc_types = [e.event_type for e in proc_events]
    assert proc_types[0] == "ProcedureRegistered"
    assert "ProcedureStarted" in proc_types
    assert proc_types[-1] == "ProcedureCompleted"
    registered = next(e for e in proc_events if e.event_type == "ProcedureRegistered")
    assert registered.payload["parent_run_id"] == str(run_id)

    # ----- INVARIANT: the parent Run gained NO new FSM state; RunStarted -> RunCompleted -----
    run_events, _ = await deps.event_store.load("Run", run_id)
    assert [e.event_type for e in run_events] == ["RunStarted", "RunCompleted"]
    completed = run_events[1].payload
    assert completed["actuation_kind"] == "Simulated"

    # ----- the volume Dataset registers against producing_run_id (NOT the Procedure) -----
    recon_dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_recon_2026-05-20_sirt_merged_engine",
            uri=artifact.uri,
            checksum_algorithm=artifact.checksum_algorithm,
            checksum_value=artifact.checksum_value,
            byte_size=96_000_000_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomoproc"}),
            producing_run_id=run_id,
            producing_procedure_id=None,
            subject_id=fixture.subject_id,
            derived_from=frozenset({fixture.raw_dataset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    recon_events, _ = await deps.event_store.load("Dataset", recon_dataset_id)
    recon_payload = recon_events[0].payload
    assert UUID(recon_payload["producing_run_id"]) == run_id
    assert recon_payload["producing_procedure_id"] is None
    # The conduct's Simulated provenance flowed Run -> Dataset (the promote gate carrier).
    assert recon_payload["producing_actuation_kind"] == "Simulated"
    assert recon_payload["derived_from"] == [str(fixture.raw_dataset_id)]

    # ----- INVARIANT: Simulated-blocks the promotion (parity with the baseline gate) -----
    await bind_promote_dataset(deps)(
        PromoteDataset(dataset_id=fixture.raw_dataset_id, reason="raw projections peer-reviewed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        await bind_promote_dataset(deps)(
            PromoteDataset(
                dataset_id=recon_dataset_id, reason="attempt to promote rehearsal recon"
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "actuation" in str(exc_info.value)
