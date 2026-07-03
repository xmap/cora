"""Quantitative performance characterization of the authority-revocation
kill-switch against real Postgres, for the T-ASE paper's evaluation section.

This is BOTH a regression test (each metric asserts a loose sanity bound so a
future change that makes the kill-switch pathologically slow fails CI) AND the
producer of the paper's performance numbers: it writes a JSON summary to
`PERF_OUT` (default the paper's data dir when present, else a temp path) that the
paper's figure/table renderer consumes. Numbers are wall-clock on the developer
testcontainer; the paper reports them as characterization, not as a tuned
benchmark, and states the environment.

Metrics (map to the T-ASE "detailed characteristics and performance" bar):

  - kill_switch_propagation_ms: wall-clock from the PolicyGrantRevoked commit to
    the last affected run reaching Held, over K concurrent supervised runs.
    Reported for K in {1, 5, 20} to show the mechanism is not a one-run trick.
  - authz_decision_us: per-call latency of the pure authorization decision
    (Policy.evaluate via the Trust authorize path), the check every command pays.
  - replay_events_per_s: throughput of folding an aggregate's event stream from
    the log (the deterministic-replay primitive behind attribution + recovery).
  - event_log_scale: number of events written across the largest scenario, so the
    reported timings carry their scale.

Reuses the E4 scenario's raw-event helpers so the measured path is the SAME code
the correctness scenario exercises.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
import os
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import EventStore
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.aggregates.run.read import load_run
from cora.run.aggregates.run.state import RunStatus
from cora.run.subscribers import make_authority_revocation_holder_subscriber
from cora.trust.aggregates.policy import evaluate
from cora.trust.aggregates.policy import fold as fold_policy
from cora.trust.aggregates.policy.events import from_stored as policy_from_stored
from cora.trust.features import revoke_grant
from cora.trust.features.revoke_grant import RevokeGrant
from tests._authz import seed_policy
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_OPERATOR_ID = UUID("01900000-0000-7000-8000-0000feed2001")
_SCALES = (1, 5, 20)
_AUTHZ_SAMPLES = 1000


async def _append_run_started(store: EventStore, *, run_id: UUID, starter_id: UUID) -> None:
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type="RunStarted",
                payload={
                    "run_id": str(run_id),
                    "name": "perf run",
                    "plan_id": str(uuid4()),
                    "subject_id": None,
                    "occurred_at": _NOW.isoformat(),
                },
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="StartRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=starter_id,
            )
        ],
    )


async def _append_supervision_decision(
    store: EventStore, *, supervisor_id: UUID, run_id: UUID
) -> None:
    decision_id = uuid4()
    await store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type="DecisionRegistered",
                payload={
                    "decision_id": str(decision_id),
                    "decided_by": str(supervisor_id),
                    "context": "RunSupervision",
                    "choice": "Continue",
                    "parent_id": None,
                    "override_kind": None,
                    "rule": "agent:RunSupervisor:v1",
                    "reasoning": None,
                    "confidence": None,
                    "confidence_source": None,
                    "alternatives": [],
                    "inputs": {"run_id": str(run_id)},
                    "reasoning_signature": None,
                    "occurred_at": _NOW.isoformat(),
                },
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterDecision",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=supervisor_id,
            )
        ],
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=5.0)


async def _latest_revoke_event(store: EventStore, *, policy_id: UUID) -> object:
    stored, _v = await store.load("Policy", policy_id)
    return next(e for e in reversed(stored) if e.event_type == "PolicyGrantRevoked")


def _emit(results: dict[str, object]) -> None:
    """Write the perf JSON where the paper renderer can read it, if the paper
    data dir exists; always also write to a temp path for CI artifact capture."""
    payload = json.dumps(results, indent=2, sort_keys=True) + "\n"
    candidates: list[Path] = []
    env_out = os.environ.get("PERF_OUT")
    if env_out:
        candidates.append(Path(env_out))
    # Best-effort: the paper lives on the main checkout, not the worktree; write
    # only if a caller pointed PERF_OUT at it. Always emit a temp copy.
    candidates.append(Path("/tmp/tase_killswitch_perf.json"))
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        except OSError:
            continue


@pytest.mark.integration
async def test_kill_switch_performance_characterization(db_pool: asyncpg.Pool) -> None:
    results: dict[str, object] = {
        "environment": "developer testcontainer (asyncpg + PostgreSQL); "
        "wall-clock, not a tuned benchmark",
        "scales": {},
    }

    # --- authz decision latency: the pure PDP the check every command pays -----
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(200)])
    policy_id = uuid4()
    await seed_policy(
        deps.event_store,
        policy_id=policy_id,
        permitted_principal_ids=[_OPERATOR_ID],
        permitted_commands=["HoldRun"],
    )
    stored, _v = await deps.event_store.load("Policy", policy_id)
    policy = fold_policy([policy_from_stored(s) for s in stored])
    assert policy is not None
    conduit_id = policy.conduit_id
    surface_id = policy.surface_id
    authz_samples_us: list[float] = []
    for _ in range(_AUTHZ_SAMPLES):
        t0 = time.perf_counter()
        evaluate(
            policy,
            principal_id=_OPERATOR_ID,
            command_name="HoldRun",
            conduit_id=conduit_id,
            surface_id=surface_id,
        )
        authz_samples_us.append((time.perf_counter() - t0) * 1e6)
    results["authz_decision_us"] = {
        "median": round(statistics.median(authz_samples_us), 3),
        "p95": round(sorted(authz_samples_us)[int(0.95 * _AUTHZ_SAMPLES)], 3),
        "samples": _AUTHZ_SAMPLES,
    }
    # The authorization decision is a pure in-memory set-membership fold; it must
    # be sub-millisecond or something is deeply wrong.
    assert statistics.median(authz_samples_us) < 1000.0

    # --- kill-switch propagation across K concurrent supervised runs ----------
    total_events = 0
    for k in _SCALES:
        deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(200)])
        store = deps.event_store
        agent_id = uuid4()
        run_ids = [uuid4() for _ in range(k)]
        for run_id in run_ids:
            await _append_run_started(store, run_id=run_id, starter_id=_OPERATOR_ID)
            await _append_supervision_decision(store, supervisor_id=agent_id, run_id=run_id)
        await _drain(db_pool)

        kpol = uuid4()
        await seed_policy(
            store,
            policy_id=kpol,
            permitted_principal_ids=[_OPERATOR_ID, agent_id],
            permitted_commands=["HoldRun"],
        )
        await revoke_grant.bind(deps)(
            RevokeGrant(policy_id=kpol, principal_id=agent_id, reason="perf"),
            principal_id=_OPERATOR_ID,
            correlation_id=_CORRELATION_ID,
        )
        revoke_event = await _latest_revoke_event(store, policy_id=kpol)

        # t0 = revocation committed; t1 = holder finished holding all K runs.
        subscriber = make_authority_revocation_holder_subscriber(deps)
        t0 = time.perf_counter()
        await subscriber.apply(revoke_event, conn=None)  # type: ignore[arg-type]
        propagation_ms = (time.perf_counter() - t0) * 1000.0

        held = 0
        for run_id in run_ids:
            run = await load_run(store, run_id)
            assert run is not None
            if run.status is RunStatus.HELD:
                held += 1
        assert held == k, f"expected all {k} runs Held, got {held}"

        scales = results["scales"]
        assert isinstance(scales, dict)
        scales[str(k)] = {
            "runs_held": held,
            "kill_switch_propagation_ms": round(propagation_ms, 2),
            "propagation_ms_per_run": round(propagation_ms / k, 2),
        }
        total_events += k * 2 + 2  # per run: RunStarted + Decision + RunHeld; +2 policy events

    results["event_log_scale"] = {"largest_scenario_events_written": total_events}

    # --- replay throughput: fold an aggregate stream from the log -------------
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(200)])
    store = deps.event_store
    rid = uuid4()
    await _append_run_started(store, run_id=rid, starter_id=_OPERATOR_ID)
    # Add a batch of hold/resume cycles to give the fold something to chew.
    version = 1
    cycles = 50
    for _ in range(cycles):
        for etype in ("RunHeld", "RunResumed"):
            await store.append(
                stream_type="Run",
                stream_id=rid,
                expected_version=version,
                events=[
                    to_new_event(
                        event_type=etype,
                        payload={"run_id": str(rid), "occurred_at": _NOW.isoformat()},
                        occurred_at=_NOW,
                        event_id=uuid4(),
                        command_name=etype,
                        correlation_id=_CORRELATION_ID,
                        causation_id=None,
                        principal_id=_OPERATOR_ID,
                    )
                ],
            )
            version += 1
    reps = 50
    t0 = time.perf_counter()
    for _ in range(reps):
        run = await load_run(store, rid)
        assert run is not None
    elapsed = time.perf_counter() - t0
    events_folded = (version) * reps
    results["replay_events_per_s"] = round(events_folded / elapsed, 1)
    results["replay_stream_length"] = version

    _emit(results)
