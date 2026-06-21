"""End-to-end integration test: Conductor + EpicsCaControlPort + Postgres.

Proves the full executor stack against real EPICS wire framing + real
Postgres. Constructs the Conductor with:

  - `EpicsCaControlPort` against the shared softIOC subprocess
    fixture (per [[project_control_port_test_isolation_research]])
  - real `start_procedure` / `complete_procedure` / `abort_procedure` /
    `append_activities` handlers bound against a real
    `PostgresEventStore` + `PostgresActivityStore` (per-test database
    cloned from the migrated template)

Walks a procedure with mixed setpoint + verify-readback + check
steps; verifies `ConductorResult` shape + Procedure FSM transition
to Completed + Activity entries landed in
`entries_operation_procedure_activities` with the expected payload shape.

Skipped under HTTP / MCP today (those are exercised at the contract
tier against the in-process InMemoryControlPort wire-up). End-to-end
HTTP-through-EPICS lands when the production wire-up grows
substrate-adapter selection from config (a follow-up iter).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
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
    WithinToleranceCriterion,
)
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.start_procedure import bind as bind_start
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020c0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020c00aa")


async def _seed_defined_procedure(deps_event_store: object, procedure_id: UUID) -> None:
    """Seed a single ProcedureRegistered event so the Procedure exists in `Defined`.

    Bypasses register_procedure (which has its own cross-aggregate
    validation paths around Capability binding + target Asset
    existence); the Conductor's start_procedure call will lift
    `Defined -> Running`.
    """
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM bakeout",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    stored = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=registered.occurred_at,
        event_id=UUID("01900000-0000-7000-8000-0000020c0001"),
        command_name="RegisterProcedure",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await deps_event_store.append(  # type: ignore[attr-defined]
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[stored],
    )


@pytest.mark.integration
async def test_conductor_runs_setpoint_check_against_real_softioc_and_postgres(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Drive a setpoint + verify-readback + check sequence against real EPICS.

    Pins the whole stack: the EpicsCaControlPort talks CA to the
    softIOC subprocess; the Conductor records each step via the real
    PostgresActivityStore; the FSM transitions Defined -> Running ->
    Completed via the real handlers + real PostgresEventStore.
    """
    procedure_id = UUID("01900000-0000-7000-8000-0000020c0100")
    logbook_id = UUID("01900000-0000-7000-8000-0000020c0101")
    open_event_id = UUID("01900000-0000-7000-8000-0000020c0102")
    started_event_id = UUID("01900000-0000-7000-8000-0000020c0103")
    setpoint_marker_id = UUID("01900000-0000-7000-8000-0000020c0104")
    setpoint_outcome_id = UUID("01900000-0000-7000-8000-0000020c0105")
    check_step_id = UUID("01900000-0000-7000-8000-0000020c0106")
    completed_event_id = UUID("01900000-0000-7000-8000-0000020c0107")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            setpoint_marker_id,
            setpoint_outcome_id,
            check_step_id,
            completed_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    start_handler = bind_start(deps)
    complete_handler = bind_complete(deps)
    abort_handler = bind_abort(deps)
    append_step_handler = bind_append(deps, step_store=step_store)
    control_port = EpicsCaControlPort()
    conductor = Conductor(
        control_port=control_port,
        append_step=append_step_handler,
        clock=deps.clock,
        id_generator=deps.id_generator,
        start_procedure=start_handler,
        complete_procedure=complete_handler,
        abort_procedure=abort_handler,
    )

    try:
        await control_port.write(f"{softioc}double_value", 42.0, wait=True)
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                SetpointStep(address=f"{softioc}double_value", value=7.5, verify=True),
                CheckStep(
                    address=f"{softioc}double_value",
                    criterion=WithinToleranceCriterion(expected=7.5, tolerance=0.01),
                ),
            ),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is True
    assert result.completed_count == 2

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

    parsed = [(r["step_kind"], r["payload"]) for r in rows]
    # The setpoint is side-effecting: it records a pre-effect in-flight
    # marker then the `ok` outcome, both round-tripping into Postgres. The
    # check (pure read) records only its outcome -- no marker.
    assert [(k, p["result"]) for k, p in parsed] == [
        ("setpoint", "in_flight"),
        ("setpoint", "ok"),
        ("check", "ok"),
    ]
    setpoint_marker = parsed[0][1]
    assert setpoint_marker["address"] == f"{softioc}double_value"
    assert setpoint_marker["value"] == 7.5
    assert "post_reading" not in setpoint_marker  # marker precedes the write

    setpoint_payload = parsed[1][1]
    assert setpoint_payload["address"] == f"{softioc}double_value"
    assert setpoint_payload["value"] == 7.5
    assert setpoint_payload["result"] == "ok"
    assert setpoint_payload["post_reading"]["value"] == 7.5
    assert setpoint_payload["post_reading"]["quality"] == "Good"

    check_payload = parsed[2][1]
    assert check_payload["address"] == f"{softioc}double_value"
    assert check_payload["criterion"] == {
        "kind": "within_tolerance",
        "expected": 7.5,
        "tolerance": 0.01,
    }
    assert check_payload["result"] == "ok"
    assert check_payload["reading"]["value"] == 7.5


@pytest.mark.integration
async def test_conductor_aborts_procedure_when_setpoint_fails_against_softioc(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """A setpoint to a nonexistent PV halts + the Conductor aborts the Procedure.

    Pins the full failure-path: real EpicsCaControlPort raises
    NotConnected for an unknown PV; Conductor records the failure +
    invokes abort_procedure; Procedure event stream lands in
    Aborted; ConductorResult.failure carries the substrate error.
    """
    procedure_id = UUID("01900000-0000-7000-8000-0000020c0200")
    started_event_id = UUID("01900000-0000-7000-8000-0000020c0201")
    logbook_id = UUID("01900000-0000-7000-8000-0000020c0202")
    open_event_id = UUID("01900000-0000-7000-8000-0000020c0203")
    setpoint_marker_id = UUID("01900000-0000-7000-8000-0000020c0204")
    setpoint_outcome_id = UUID("01900000-0000-7000-8000-0000020c0205")
    aborted_event_id = UUID("01900000-0000-7000-8000-0000020c0206")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            setpoint_marker_id,
            setpoint_outcome_id,
            aborted_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    control_port = EpicsCaControlPort(default_timeout_s=0.3)
    conductor = Conductor(
        control_port=control_port,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )

    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(SetpointStep(address=f"{softioc}does_not_exist", value=1.0),),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.source_kind == "setpoint"
    assert result.failure.error_class == "ControlNotConnectedError"

    async with db_pool.acquire() as conn:
        event_types = await conn.fetch(
            """
            SELECT event_type FROM events
            WHERE stream_type = 'Procedure' AND stream_id = $1
            ORDER BY version
            """,
            procedure_id,
        )
    types = [r["event_type"] for r in event_types]
    assert types[0] == "ProcedureRegistered"
    assert "ProcedureStarted" in types
    assert types[-1] == "ProcedureAborted"


@pytest.mark.integration
async def test_conductor_completes_procedure_with_equals_check_against_softioc(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """Setpoint long_value + check EqualsCriterion against an integer reading."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020c0300")
    started_event_id = UUID("01900000-0000-7000-8000-0000020c0301")
    logbook_id = UUID("01900000-0000-7000-8000-0000020c0302")
    open_event_id = UUID("01900000-0000-7000-8000-0000020c0303")
    setpoint_marker_id = UUID("01900000-0000-7000-8000-0000020c0304")
    setpoint_outcome_id = UUID("01900000-0000-7000-8000-0000020c0305")
    check_step_id = UUID("01900000-0000-7000-8000-0000020c0306")
    completed_event_id = UUID("01900000-0000-7000-8000-0000020c0307")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            setpoint_marker_id,
            setpoint_outcome_id,
            check_step_id,
            completed_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    control_port = EpicsCaControlPort()
    conductor = Conductor(
        control_port=control_port,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )

    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                SetpointStep(address=f"{softioc}long_value", value=99),
                CheckStep(
                    address=f"{softioc}long_value",
                    criterion=EqualsCriterion(expected=99),
                ),
            ),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is True
    assert result.completed_count == 2
