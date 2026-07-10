"""Performance characterization of the actor-symmetry kill-switch, against real Postgres.

Measures the three quantities the actor-symmetry paper reports and, when
`CORA_PERF_OUT` is set, writes them as JSON (the paper's
`data/killswitch_perf.json`); otherwise it just asserts the characterization
holds. All numbers are wall-clock on the developer testcontainer
(`pgvector/pgvector:pg18` via testcontainers, asyncpg), single-threaded, not a
tuned benchmark.

Three measurements:
  - authz-decision latency: the pure Policy `evaluate` (no I/O), batch-sampled.
  - event-replay throughput: folding a 100-event Run stream in memory (`fold`),
    isolating the pure left-fold from DB IO and deserialization.
  - kill-switch propagation vs K concurrent supervised runs: one
    `PolicyGrantRevoked` delivered to the holder subscriber holds all K of the
    revoked principal's Running runs; we time that `apply()` and confirm K/K
    land in Held. K is swept so the figure can show total time and per-run cost.

Attribution is by the RunStarted envelope principal (the involvement projection's
key), so seeding one RunStarted per run with `principal_id=starter` is enough to
make the holder discover and hold it.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

import json
import os
import statistics
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_authority_revocation_holder import seed_authority_revocation_holder_agent
from cora.agent.subscribers.authority_revocation_holder import (
    make_authority_revocation_holder_subscriber,
)
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import UUIDv7Generator
from cora.infrastructure.ports.event_store import NewEvent, StoredEvent
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run.adapters import PostgresRunActorInvolvementLookup
from cora.run.aggregates.run import RunStatus, load_run
from cora.run.aggregates.run.events import RunCompleted, RunHeld, RunResumed, RunStarted
from cora.run.aggregates.run.evolver import fold
from cora.run.projections import RunActorInvolvementProjection
from cora.trust.aggregates.policy.state import Policy, PolicyName, evaluate
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
_CORR = UUID("01900000-0000-7000-8000-0000000000cc")

_K_SWEEP = (1, 2, 5, 10, 20, 50)
_AUTHZ_SAMPLES = 2000
_AUTHZ_BATCH = 200
_REPLAY_STREAM = 100
_REPLAY_ITERS = 20000

_ENVIRONMENT = (
    "developer testcontainer (pgvector/pgvector:pg18 via testcontainers, asyncpg); "
    "wall-clock, single-threaded, not a tuned benchmark"
)


def _write_perf_json(path: str, result: Mapping[str, object]) -> None:
    """Sync JSON write, kept off the async test body (ASYNC230)."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")


def _authz_decision_us() -> dict[str, float | int]:
    """Batch-sampled latency of the pure Policy decision (no I/O, no events)."""
    principal, conduit, surface = uuid4(), uuid4(), uuid4()
    policy = Policy(
        id=uuid4(),
        name=PolicyName("perf-bench"),
        conduit_id=conduit,
        permitted_principal_ids=frozenset({principal, *(uuid4() for _ in range(63))}),
        permitted_commands=frozenset({"HoldRun", "StartRun", *(f"Cmd{i}" for i in range(30))}),
        surface_id=surface,
    )

    def _call() -> None:
        evaluate(
            policy,
            principal_id=principal,
            command_name="HoldRun",
            conduit_id=conduit,
            surface_id=surface,
        )

    for _ in range(2000):  # warm the interpreter / caches
        _call()

    per_call_us: list[float] = []
    for _ in range(_AUTHZ_SAMPLES):
        t0 = time.perf_counter_ns()
        for _ in range(_AUTHZ_BATCH):
            _call()
        per_call_us.append((time.perf_counter_ns() - t0) / 1000.0 / _AUTHZ_BATCH)
    per_call_us.sort()
    return {
        "median": statistics.median(per_call_us),
        "p95": per_call_us[int(0.95 * len(per_call_us))],
        "samples": _AUTHZ_SAMPLES,
    }


def _replay_throughput() -> dict[str, float | int]:
    """Pure in-memory fold throughput of a 100-event Run stream."""
    rid = uuid4()
    events: list[object] = [
        RunStarted(
            run_id=rid, name="perf-bench", plan_id=uuid4(), subject_id=uuid4(), occurred_at=_NOW
        )
    ]
    while len(events) < _REPLAY_STREAM - 1:
        events.append(RunHeld(run_id=rid, occurred_at=_NOW))
        events.append(RunResumed(run_id=rid, occurred_at=_NOW))
    events.append(RunCompleted(run_id=rid, occurred_at=_NOW))

    for _ in range(1000):  # warm
        fold(events)  # type: ignore[arg-type]

    t0 = time.perf_counter()
    for _ in range(_REPLAY_ITERS):
        fold(events)  # type: ignore[arg-type]
    elapsed = time.perf_counter() - t0
    return {
        "events_per_s": _REPLAY_ITERS * len(events) / elapsed,
        "stream_length": len(events),
    }


async def _seed_running_run(store: PostgresEventStore, *, run_id: UUID, starter: UUID) -> None:
    """Append one RunStarted whose envelope principal is `starter`.

    The five payload keys are the minimum the holder's fold needs (run_id, name,
    plan_id, subject_id present, occurred_at); plan_id/subject_id are not
    existence-checked at fold time.
    """
    payload = {
        "run_id": str(run_id),
        "name": f"perf-run-{run_id}",
        "plan_id": str(uuid4()),
        "subject_id": None,
        "occurred_at": _NOW.isoformat(),
    }
    await store.append(
        "Run",
        run_id,
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type="RunStarted",
                schema_version=1,
                payload=payload,
                occurred_at=_NOW,
                correlation_id=_CORR,
                causation_id=None,
                metadata={},
                principal_id=starter,
            )
        ],
    )


def _revocation_event(*, revoked_principal_id: UUID) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Policy",
        stream_id=uuid4(),
        version=1,
        event_type="PolicyGrantRevoked",
        schema_version=1,
        payload={
            "policy_id": str(uuid4()),
            "principal_id": str(revoked_principal_id),
            "revoked_by": str(uuid4()),
            "reason": "trust withdrawn",
            "occurred_at": _NOW.isoformat(),
        },
        correlation_id=_CORR,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


async def _time_killswitch(
    db_pool: asyncpg.Pool, deps: Kernel, store: PostgresEventStore, k: int
) -> tuple[float, int]:
    """Seed K Running runs for a fresh principal, revoke, time the hold, count held."""
    revoked = uuid4()
    run_ids = [uuid4() for _ in range(k)]
    for run_id in run_ids:
        await _seed_running_run(store, run_id=run_id, starter=revoked)

    registry = ProjectionRegistry()
    registry.register(RunActorInvolvementProjection())
    await drain_projections(db_pool, registry, deadline_seconds=15.0)

    holder = make_authority_revocation_holder_subscriber(deps)
    event = _revocation_event(revoked_principal_id=revoked)

    t0 = time.perf_counter()
    await holder.apply(event, conn=None)  # type: ignore[arg-type]
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    held = 0
    for run_id in run_ids:
        state = await load_run(deps.event_store, run_id)
        if state is not None and state.status is RunStatus.HELD:
            held += 1
    return elapsed_ms, held


@pytest.mark.integration
async def test_authority_revocation_perf_characterizes_authz_replay_and_killswitch(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        id_generator=UUIDv7Generator(),
        run_actor_involvement_lookup=PostgresRunActorInvolvementLookup(db_pool),
    )
    await seed_authority_revocation_holder_agent(deps)
    store = PostgresEventStore(db_pool)

    scales: dict[str, dict[str, float | int]] = {}
    for k in _K_SWEEP:
        elapsed_ms, held = await _time_killswitch(db_pool, deps, store, k)
        scales[str(k)] = {
            "kill_switch_propagation_ms": round(elapsed_ms, 2),
            "propagation_ms_per_run": round(elapsed_ms / k, 2),
            "runs_held": held,
        }

    authz = _authz_decision_us()
    replay = _replay_throughput()

    result = {
        "authz_decision_us": {
            "median": round(float(authz["median"]), 3),
            "p95": round(float(authz["p95"]), 3),
            "samples": int(authz["samples"]),
        },
        "replay_events_per_s": round(float(replay["events_per_s"]), 1),
        "replay_stream_length": int(replay["stream_length"]),
        "environment": _ENVIRONMENT,
        "scales": scales,
    }

    out = os.environ.get("CORA_PERF_OUT")
    if out:
        _write_perf_json(out, result)
    print("\nKILLSWITCH_PERF " + json.dumps(result))

    # The characterization must actually hold, not merely produce numbers.
    for k in _K_SWEEP:
        assert scales[str(k)]["runs_held"] == k, (
            f"K={k}: only {scales[str(k)]['runs_held']}/{k} held"
        )
    assert float(authz["median"]) < 5.0
    assert float(replay["events_per_s"]) > 10_000.0
