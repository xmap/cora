"""End-to-end integration test: pause to Held, then resume and replay.

`conduct_or_hold` -> `conduct_from` against real EPICS wire framing and
real Postgres, which is the pair `test_conductor_against_softioc_postgres.py`
does not cover: that file drives `conduct` only, so its Procedures reach
Completed or Aborted and never park.

Why this file exists. Until it did, `conduct_from` appeared in unit and
contract tests only and in no integration test at all, so the resume path
had never once run against a database and a control port together. Every
other rung of the pilot's ladder rides on a rehearsal at this tier before
it is attempted on the floor, and this one did not have one.

The pause is not injected. A check whose criterion does not hold is a
RECOVERABLE failure (`_is_recoverable_failure`), so a step list whose
check cannot pass yet parks the Procedure at Held on its own, which is
the same shape a real conduct produces when a device has not reached the
value the recipe asked for. The operator then makes the world match and
resumes, and the check is re-run as a fresh gate rather than assumed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    ProcedureRegistered,
    event_type_name,
    to_payload,
)
from cora.operation.conductor import (
    CheckStep,
    Conductor,
    EqualsCriterion,
    SetpointStep,
)
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.hold_procedure import bind as bind_hold
from cora.operation.features.resume_procedure import bind as bind_resume
from cora.operation.features.start_procedure import bind as bind_start
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020d0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020d00aa")

# The boundary the resume replays from: index of the check that failed.
# Single-sourced here because it rides into both `ProcedureResumed` and
# `execute_from`, and a test that wrote it twice could pass with the two
# disagreeing.
_BOUNDARY = 1


def _ids(count: int) -> list[UUID]:
    """A generous queue of distinct ids for `FixedIdGenerator`.

    Named per-event ids the way the sibling conduct test does them would
    have to be counted exactly across TWO conducts plus a hold and a
    resume, and no assertion here reads an event id. Exhaustion raises
    `FixedIdGeneratorExhaustedError` loudly, so over-supplying hides
    nothing.

    The range starts high to stay clear of the fixed ids above and of the
    seed event's own id. An earlier version began at 1 and handed the
    seed's id back out as the first generated one, which surfaced as a
    `UniqueViolationError` on `ProcedureStarted` and then, because
    `conduct_or_hold` suppresses a failed hold, as a bare `held=False`
    with a lifecycle failure buried in the result.
    """
    return [UUID(f"01900000-0000-7000-8000-0000020d{n:04x}") for n in range(0x1000, 0x1000 + count)]


async def _seed_defined_procedure(deps: Kernel, procedure_id: UUID) -> None:
    """Seed one ProcedureRegistered so the Procedure exists in `Defined`.

    Same bypass as the sibling conduct test: register_procedure carries
    cross-aggregate validation this file is not exercising.
    """
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM alignment settle",
        kind="commissioning",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    stored = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=registered.occurred_at,
        event_id=UUID("01900000-0000-7000-8000-0000020d0001"),
        command_name="RegisterProcedure",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[stored],
    )


def _conductor(
    db_pool: asyncpg.Pool, softioc: str, deps: Kernel
) -> tuple[Conductor, ControlPortRegistry]:
    """Build a resume-capable Conductor and hand back its control port.

    The port comes back because the caller has to `aclose()` it, and it is
    the same instance across both conducts here on purpose: a resume in
    production runs against a fresh port, but sharing one keeps this test
    about the FSM and the replay rather than about adapter lifetime.
    """
    adapter = EpicsCaControlPort()
    control_port = ControlPortRegistry()
    control_port.register_substrate_port(softioc, adapter, "epics_ca")
    conductor = Conductor(
        control_port=control_port,
        append_step=bind_append(deps, step_store=PostgresActivityStore(db_pool)),
        clock=deps.clock,
        id_generator=deps.id_generator,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
        hold_procedure=bind_hold(deps),
        resume_procedure=bind_resume(deps),
    )
    return conductor, control_port


async def _procedure_event_types(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[str]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_type FROM events
            WHERE stream_type = 'Procedure' AND stream_id = $1
            ORDER BY version
            """,
            procedure_id,
        )
    return [r["event_type"] for r in rows]


@pytest.mark.integration
async def test_conduct_or_hold_parks_at_held_then_conduct_from_replays_the_tail(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """A failed check parks the Procedure; the resume re-runs it and completes.

    Pins the whole resume path end to end: real EpicsCaControlPort against
    the softIOC subprocess, real hold / resume / complete handlers against
    a real PostgresEventStore, real activity rows in Postgres.
    """
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0100")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_ids(40))
    await _seed_defined_procedure(deps, procedure_id)
    conductor, control_port = _conductor(db_pool, softioc, deps)

    # long_value starts at 0, so the check below cannot hold yet. This is
    # the world the operator has to fix before the resume is worth issuing.
    steps = (
        SetpointStep(address=f"{softioc}double_value", value=7.5, verify=True),
        CheckStep(address=f"{softioc}long_value", criterion=EqualsCriterion(expected=99)),
    )

    try:
        await control_port.write(f"{softioc}long_value", 0, wait=True)

        paused = await conductor.conduct_or_hold(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=steps,
        )

        # The Procedure is parked, not terminal, and the setpoint that DID
        # land is reported as left set. A hold is best-effort inside
        # `conduct_or_hold`, so `held` is asserted rather than inferred from
        # the absence of an exception.
        assert paused.succeeded is False
        assert paused.held is True
        assert paused.completed_count == _BOUNDARY
        assert paused.failure is not None
        assert paused.failure.source_kind == "check"
        assert paused.failure.step_index == _BOUNDARY
        assert paused.substrate_writes == {f"{softioc}double_value": 7.5}

        assert await _procedure_event_types(db_pool, procedure_id) == [
            "ProcedureRegistered",
            "ProcedureStarted",
            "ProcedureActivitiesLogbookOpened",
            "ProcedureHeld",
        ]

        # The operator makes the world match what the recipe asked for.
        await control_port.write(f"{softioc}long_value", 99, wait=True)

        resumed = await conductor.conduct_from(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=steps,
            boundary=_BOUNDARY,
        )
    finally:
        await control_port.aclose()

    assert resumed.succeeded is True
    # No acquisition-halt assertion here: `acquisition_halt` is derived by
    # the slice handler (`is_acquisition_halt`), not carried on
    # `ConductorResult`. A halt would leave the Procedure Running with no
    # ProcedureCompleted, which the event-type assertion below already pins.
    # Only the tail ran. A resume that re-drove the whole list would report
    # 2 here and would also have re-written double_value.
    assert resumed.completed_count == len(steps) - _BOUNDARY
    assert resumed.substrate_writes == {}

    assert await _procedure_event_types(db_pool, procedure_id) == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureHeld",
        "ProcedureResumed",
        "ProcedureCompleted",
    ]

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT step_kind, payload
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1
            ORDER BY sampled_at, event_id
            """,
            procedure_id,
        )
    journal = [(r["step_kind"], r["payload"]["result"], r["payload"]["step_index"]) for r in rows]

    # The pre-boundary setpoint appears ONCE, from the first conduct. The
    # check appears twice, failed then ok, both at the same step index:
    # the replay reuses the pinned list's own indices rather than
    # renumbering from the boundary, which is what lets a reader line the
    # second attempt up against the first.
    assert journal == [
        ("setpoint", "in_flight", 0),
        ("setpoint", "ok", 0),
        ("check", "failed", _BOUNDARY),
        ("check", "ok", _BOUNDARY),
    ]


@pytest.mark.integration
async def test_conduct_from_aborts_when_the_replayed_check_still_fails(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Resuming without fixing the world re-runs the gate and aborts.

    The companion to the happy path, and the one that proves the replayed
    check is a fresh gate rather than a formality. A resume that assumed
    the boundary step would now pass, or that skipped it as already
    attempted, would reach Completed here.
    """
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0200")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_ids(40))
    await _seed_defined_procedure(deps, procedure_id)
    conductor, control_port = _conductor(db_pool, softioc, deps)

    steps = (
        SetpointStep(address=f"{softioc}double_value", value=7.5, verify=True),
        CheckStep(address=f"{softioc}long_value", criterion=EqualsCriterion(expected=99)),
    )

    try:
        await control_port.write(f"{softioc}long_value", 0, wait=True)
        paused = await conductor.conduct_or_hold(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=steps,
        )
        assert paused.held is True

        # Nothing is fixed between the hold and the resume.
        resumed = await conductor.conduct_from(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=steps,
            boundary=_BOUNDARY,
        )
    finally:
        await control_port.aclose()

    assert resumed.succeeded is False
    assert resumed.completed_count == 0
    assert resumed.failure is not None
    assert resumed.failure.source_kind == "check"

    # Aborted, not held again: `conduct_from` terminalizes on a genuine step
    # failure. A Procedure cannot pause twice on the same boundary, which
    # is what stops a resume loop from parking forever.
    assert await _procedure_event_types(db_pool, procedure_id) == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureHeld",
        "ProcedureResumed",
        "ProcedureAborted",
    ]
