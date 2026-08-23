"""S2a's exit criterion: every registered logbook kind is proven reachable
(or proven not) by a real seeder, end to end through `export_bundle`.

Per `project_record_completeness_design.md`'s S2a: `_SEEDERS` is keyed on
`spec.kind` and parametrized over `all_specs()`. A kind with no entry
here raises `KeyError` on `_SEEDERS[spec.kind]` -- a bracket lookup,
never `.get()` -- so a registered kind cannot be added without someone
proving it is reachable (or genuinely not) by writing its seeder. Each
seeder puts real rows into the database through the real production
handler for its kind (never raw SQL), following the pattern
`test_record_export_shell_postgres.py` (added by S1) established for
`activity`. The BLEPS supply observer slice's `supply_probe` (the
tenth registered kind) is the first kind to land exactly the way this
docstring predicted.

`heartbeat` (S5a), `capture_probe` (S5b), `permit_probe` (S5c) and
`supply_probe` each declare an `unscoped_reader` now, so all four are
expected to come out `included` like the six envelope-driven kinds,
even though none of them has an envelope of its own; the
`reachable`/`included` branch below is computed from the registry, not
hardcoded per kind, so it tracks whichever kinds are wired without
needing an update here when a kind's spec changes. No registered kind
is expected to come out `untraversed`
in this test any more -- before S2a, the shipped
`row_count_by_logbook_kind` field could not even describe that case
(`{}` is what the original defect reported for two genuinely populated
kinds); after S2a the manifest said `untraversed` in writing, and after
S5c no registered kind reaches that branch in production (see
`test_manifest.py`'s own construction of the state for where it is
still exercised).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.decision.aggregates.decision import (
    DECISION_REASONING_OPERATION_CHAT,
    PostgresInferenceStore,
)
from cora.decision.features.append_inferences import AppendInferences, ReasoningEntryInput
from cora.decision.features.append_inferences import bind as bind_append_inferences
from cora.decision.features.register_decision import RegisterDecision
from cora.decision.features.register_decision import bind as bind_register_decision
from cora.enclosure.aggregates.enclosure import PermitProbe, PostgresPermitProbeStore
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import Allow, FakeClock, FixedIdGenerator
from cora.infrastructure.record_export import all_specs, export_bundle
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    PostgresDiagnosticStore,
    PostgresOutcomeStore,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    to_payload,
)
from cora.operation.features.append_activities import ActivityInput, AppendProcedureActivities
from cora.operation.features.append_activities import bind as bind_append_activities
from cora.operation.features.append_diagnostics import AppendProcedureDiagnostics, DiagnosticInput
from cora.operation.features.append_diagnostics import bind as bind_append_diagnostics
from cora.operation.features.append_outcomes import AppendProcedureOutcomes, OutcomeInput
from cora.operation.features.append_outcomes import bind as bind_append_outcomes
from cora.run.aggregates.run import (
    CaptureProbe,
    FeedHeartbeat,
    PostgresCaptureProbeStore,
    PostgresFeedHeartbeatStore,
    PostgresObservationStore,
)
from cora.run.aggregates.run.events import RunStarted
from cora.run.aggregates.run.events import event_type_name as run_event_type_name
from cora.run.aggregates.run.events import to_payload as run_to_payload
from cora.run.features.append_observations import AppendObservations, ObservationInput
from cora.run.features.append_observations import bind as bind_append_observations
from cora.shared.identity import ActorId
from cora.shared.reach import ReachTier
from cora.supply.aggregates.supply import PostgresSupplyProbeStore, SupplyProbe
from cora.trust.aggregates.conduit.entries import PostgresVerdictStore
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit
from tests._authz import seed_policy
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(event_store: object, procedure_id: UUID) -> None:
    """Same shape as `test_record_export_shell_postgres.py`'s helper:
    `ProcedureRegistered` + `ProcedureStarted` appended directly, bypassing
    `register_procedure`/`start_procedure`'s cross-aggregate validation."""
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="Vessel-A bakeout",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    started = ProcedureStarted(procedure_id=procedure_id, occurred_at=_NOW)
    for index, event in enumerate((registered, started)):
        new_event = to_new_event(
            event_type=event_type_name(event),
            payload=to_payload(event),
            occurred_at=event.occurred_at,
            event_id=uuid4(),
            command_name="RegisterProcedure" if index == 0 else "StartProcedure",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
        await event_store.append(  # type: ignore[attr-defined]
            stream_type="Procedure",
            stream_id=procedure_id,
            expected_version=index,
            events=[new_event],
        )


async def _seed_verdict(db_pool: asyncpg.Pool) -> None:
    """Mirrors `test_trust_authorize_verdicts_postgres.py`: define a
    Conduit, seed a Policy directly, wire `TrustAuthorize` with a real
    `PostgresVerdictStore`, issue one Allow."""
    event_store = PostgresEventStore(db_pool)
    verdict_store = PostgresVerdictStore(db_pool)
    conduit_id = uuid4()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[conduit_id, uuid4(), uuid4(), uuid4()],
        event_store=event_store,
    )
    await define_conduit.bind(deps)(
        DefineConduit(name="Detector-to-Storage", source_zone_id=uuid4(), target_zone_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    policy_id = uuid4()
    await seed_policy(
        event_store,
        policy_id=policy_id,
        permitted_principal_ids={_PRINCIPAL_ID},
        permitted_commands={"RegisterActor"},
        conduit_id=conduit_id,
        occurred_at=_NOW,
    )
    authorize = TrustAuthorize(
        event_store,
        policy_id=policy_id,
        verdict_store=verdict_store,
        clock=FakeClock(_NOW),
        id_generator=FixedIdGenerator([uuid4()]),
    )
    result = await authorize.authorize(_PRINCIPAL_ID, "RegisterActor", conduit_id)
    assert isinstance(result, Allow)


async def _seed_inference(db_pool: asyncpg.Pool) -> None:
    """Mirrors `test_append_inferences_handler_postgres.py`: register an
    Actor + a Decision, then append one reasoning entry."""
    actor_id = ActorId(uuid4())
    deps = build_postgres_deps(
        db_pool, now=_NOW, ids=[actor_id, uuid4(), uuid4(), uuid4(), uuid4(), uuid4()]
    )
    await bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))(
        RegisterActor(name="AI Reviewer"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    decision_id = await bind_register_decision(deps)(
        RegisterDecision(
            decided_by=actor_id,
            context="RecipeApproval",
            choice="Approved",
            parent_id=None,
            override_kind=None,
            rule=None,
            reasoning=None,
            confidence=0.92,
            confidence_source=None,
            alternatives=(),
            inputs=None,
            reasoning_signature=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_append_inferences(deps, inference_store=PostgresInferenceStore(db_pool))(
        AppendInferences(
            decision_id=decision_id,
            entries=(
                ReasoningEntryInput(
                    event_id=uuid4(),
                    occurred_at=_NOW,
                    operation_name=DECISION_REASONING_OPERATION_CHAT,
                    provider_name="anthropic",
                    request_model="claude-opus-4-7",
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_activity(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    await _seed_running_procedure(deps.event_store, procedure_id)
    await bind_append_activities(deps, step_store=PostgresActivityStore(db_pool))(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                ActivityInput(
                    event_id=uuid4(),
                    step_kind="setpoint",
                    payload={"channel": "T_oven", "target_value": 423.0},
                    sampled_at=_NOW,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_diagnostic(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    await _seed_running_procedure(deps.event_store, procedure_id)
    await bind_append_diagnostics(deps, diagnostic_store=PostgresDiagnosticStore(db_pool))(
        AppendProcedureDiagnostics(
            procedure_id=procedure_id,
            entries=(
                DiagnosticInput(
                    event_id=uuid4(),
                    iteration_index=1,
                    model_ref="botorch",
                    payload={"lengthscale_offset": 0.8, "noise": 0.005, "acquisition_value": 0.12},
                    sampled_at=_NOW,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_outcome(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    await _seed_running_procedure(deps.event_store, procedure_id)
    await bind_append_outcomes(deps, outcome_store=PostgresOutcomeStore(db_pool))(
        AppendProcedureOutcomes(
            procedure_id=procedure_id,
            entries=(
                OutcomeInput(
                    event_id=uuid4(),
                    iteration_index=0,
                    point={"energy": 8.0},
                    measurements=[
                        {"name": "flux", "value": 12.5, "kind": "Scalar", "quality": "Good"}
                    ],
                    succeeded=True,
                    actuation_kind="Physical",
                    sampled_at=_NOW,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_observation(db_pool: asyncpg.Pool) -> None:
    """Mirrors `test_append_observations_handler_postgres.py`: a bare
    `RunStarted` seeded directly (bypassing `start_run`'s upstream
    chain), then one observation appended."""
    run_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    event = RunStarted(
        run_id=run_id,
        name="Integration-test Run",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(event),
        payload=run_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event]
    )
    await bind_append_observations(deps, observation_store=PostgresObservationStore(db_pool))(
        AppendObservations(
            run_id=run_id,
            entries=(
                ObservationInput(
                    event_id=uuid4(),
                    channel_name="T_sample",
                    value=295.1,
                    sampled_at=_NOW,
                    sampling_procedure="baseline",
                    units="K",
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_heartbeat(db_pool: asyncpg.Pool) -> None:
    """`entries_run_feed_heartbeats` has no FK and no envelope: the real
    production writer is `PostgresFeedHeartbeatStore.append`, called
    directly by `CaptureProgressFeeder`/`RunWitnessRecorder` rather than
    through a CQRS command handler. Calling the store directly IS the
    real path; there is no handler wrapper to go through."""
    store = PostgresFeedHeartbeatStore(db_pool)
    await store.append(
        [FeedHeartbeat(event_id=uuid4(), run_id=uuid4(), source_id="epics", heartbeat_at=_NOW)]
    )


async def _seed_permit_probe(db_pool: asyncpg.Pool) -> None:
    """`entries_enclosure_permit_probes` has no FK either; the real
    production writer is `PostgresPermitProbeStore.append`, called by
    the enclosure permit monitor (`cora.enclosure._monitor`)."""
    store = PostgresPermitProbeStore(db_pool)
    await store.append(
        [
            PermitProbe(
                event_id=uuid4(),
                enclosure_id=uuid4(),
                source_kind="EpicsPv",
                source_id="2bma:hutch:permit",
                reach_tier=ReachTier.RELAYED,
                status_claimed=True,
            )
        ]
    )


async def _seed_capture_probe(db_pool: asyncpg.Pool) -> None:
    """`capture_code` has no backing aggregate at all, by design; the
    real production writer is `PostgresCaptureProbeStore.append`."""
    store = PostgresCaptureProbeStore(db_pool)
    await store.append(
        [
            CaptureProbe(
                event_id=uuid4(),
                capture_code=f"2bmb-tomoscan-{uuid4().hex[:8]}",
                source_kind="EpicsPv",
                source_id="2bmb:TomoScan:ScanStatus",
                reach_tier=ReachTier.RELAYED,
                phase_claimed=True,
                observed_at=_NOW,
            )
        ]
    )


async def _seed_supply_probe(db_pool: asyncpg.Pool) -> None:
    """`entries_supply_probes` has no FK either; the real production
    writer is `PostgresSupplyProbeStore.append`, called by the Supply
    status monitor (`cora.supply._monitor`)."""
    store = PostgresSupplyProbeStore(db_pool)
    await store.append(
        [
            SupplyProbe(
                event_id=uuid4(),
                supply_id=uuid4(),
                source_kind="EpicsPv",
                source_id="2bmBLEPS:BLEPS:FLOW2_TRIP",
                reach_tier=ReachTier.RELAYED,
                status_claimed=True,
            )
        ]
    )


_SEEDERS: dict[str, Callable[[asyncpg.Pool], Awaitable[None]]] = {
    "verdict": _seed_verdict,
    "inference": _seed_inference,
    "activity": _seed_activity,
    "diagnostic": _seed_diagnostic,
    "outcome": _seed_outcome,
    "observation": _seed_observation,
    "heartbeat": _seed_heartbeat,
    "permit_probe": _seed_permit_probe,
    "capture_probe": _seed_capture_probe,
    "supply_probe": _seed_supply_probe,
}


@pytest.mark.integration
@pytest.mark.parametrize("spec", all_specs(), ids=lambda spec: spec.kind)
async def test_manifest_accounts_for_every_registered_kind(
    db_pool: asyncpg.Pool, tmp_path: Path, spec: object
) -> None:
    # Bracket access, not `.get()`: a kind with no seeder here must raise
    # KeyError rather than being silently skipped over.
    seeder = _SEEDERS[spec.kind]  # type: ignore[attr-defined]
    await seeder(db_pool)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        bundle = await export_bundle(pg_conn, tmp_path / "bundle")

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    extent = manifest["extent_by_logbook_kind"]

    assert set(extent) == {s.kind for s in all_specs()}, (
        "extent_by_logbook_kind must carry a slot for every registered kind, "
        "not only the one this test seeded"
    )

    reachable = (
        spec.envelope_class is not None or spec.unscoped_reader is not None  # type: ignore[attr-defined]
    )
    if reachable:
        assert extent[spec.kind]["status"] == "included"  # type: ignore[attr-defined]
        assert extent[spec.kind]["exported_row_count"] >= 1  # type: ignore[attr-defined]
        # This line cannot fail on its own: reaching it already required
        # export_bundle to succeed, which already required source ==
        # exported, and the line above already pins exported >= 1. It is
        # not itself the anti-degeneracy guard; the guard is this test's
        # OWN parametrization over every spec in all_specs() combined with
        # the build-time raise in _extent_by_logbook_kind -- a
        # capture_source_row_count_by_logbook_kind that vacuously returned
        # 0 for every kind (the shape a broken counter takes, and the
        # shape that would pass unnoticed on the pilot database, where most
        # of the ten kinds hold zero rows on an ordinary day) would make
        # EVERY seeded kind here raise LogbookKindRowCountMismatchError
        # before this bundle ever existed, failing this whole test.
        assert extent[spec.kind]["source_row_count"] >= 1  # type: ignore[attr-defined]
    else:
        # No registered kind reaches this branch today (S5c wired the
        # last of the three no-envelope kinds, `permit_probe`), but the
        # branch stays: a future kind registered with neither an
        # envelope nor an unscoped reader would seed real rows here (the
        # seeder above just wrote them) that no code path reads into the
        # export, so the manifest must say so rather than silently
        # reporting a coverage field that agrees with the traversal by
        # construction.
        assert extent[spec.kind]["status"] == "untraversed"  # type: ignore[attr-defined]
        assert extent[spec.kind]["exported_row_count"] == 0  # type: ignore[attr-defined]
