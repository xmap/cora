"""End-to-end integration test: acquisition action bodies + softIOC + Postgres.

Mirrors `test_conductor_against_softioc_postgres.py` for the
substrate-neutral scan primitives `collect` / `discrete` / `continuous`.
Constructs the Conductor with:

  - `EpicsCaControlPort` against the shared softIOC subprocess fixture
    (per [[project_control_port_test_isolation_research]])
  - `InMemoryActionRegistry` seeded with the three production action
    bodies from `cora.operation.acquisitions`
  - real handlers bound against `PostgresEventStore` + `PostgresActivityStore`

The softIOC carries an areaDetector ADCore-shaped PV family
(`cam1:TriggerMode` / `:AcquireTime` / `:NumImages` / `:Acquire` /
`:Acquire_RBV` / `:DetectorState_RBV`) plus the existing writable
`double_value` scalar used as the axis for `discrete` + `continuous`.
`cam1:Acquire_RBV` starts at `0` (Done) so each body's poll loop exits
on the first read; the integration tier proves wire framing + record
routing, not the detector finite-state machine. Detector mid-flight
timing (Acquire_RBV staying 1 until pulses complete) is covered at the
unit tier via the IteratingPort fixture.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.operation.acquisitions import collect, continuous, discrete
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    ProcedureRegistered,
    event_type_name,
    to_payload,
)
from cora.operation.conductor import (
    ActionStep,
    Conductor,
    InMemoryActionRegistry,
)
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.start_procedure import bind as bind_start
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020d0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020d00aa")

_ACTION_REGISTRY = InMemoryActionRegistry(
    {"collect": collect, "discrete": discrete, "continuous": continuous}
)


async def _seed_defined_procedure(deps_event_store: object, procedure_id: UUID) -> None:
    """Seed a single ProcedureRegistered event so the Procedure exists in Defined."""
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM acquisition smoke",
        kind="bakeout",
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
    await deps_event_store.append(  # type: ignore[attr-defined]
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[stored],
    )


def _build_conductor(
    deps_event_store: object,
    db_pool: asyncpg.Pool,
    control_port: EpicsCaControlPort,
    *,
    clock: object,
    id_generator: object,
    start: object,
    complete: object,
    abort: object,
    append: object,
) -> Conductor:
    _ = (deps_event_store, db_pool)  # surfaced in the per-test deps closure
    return Conductor(
        control_port=control_port,
        append_step=append,  # type: ignore[arg-type]
        clock=clock,  # type: ignore[arg-type]
        id_generator=id_generator,  # type: ignore[arg-type]
        action_registry=_ACTION_REGISTRY,
        start_procedure=start,  # type: ignore[arg-type]
        complete_procedure=complete,  # type: ignore[arg-type]
        abort_procedure=abort,  # type: ignore[arg-type]
    )


@pytest.mark.integration
async def test_conductor_runs_collect_action_against_real_softioc_and_postgres(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """The `collect` body talks real CA to the AD PV family + records evidence."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0100")
    started_event_id = UUID("01900000-0000-7000-8000-0000020d0101")
    logbook_id = UUID("01900000-0000-7000-8000-0000020d0102")
    open_event_id = UUID("01900000-0000-7000-8000-0000020d0103")
    collect_marker_id = UUID("01900000-0000-7000-8000-0000020d0104")
    collect_step_id = UUID("01900000-0000-7000-8000-0000020d0105")
    completed_event_id = UUID("01900000-0000-7000-8000-0000020d0106")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            collect_marker_id,
            collect_step_id,
            completed_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    control_port = EpicsCaControlPort()
    conductor = _build_conductor(
        deps.event_store,
        db_pool,
        control_port,
        clock=deps.clock,
        id_generator=deps.id_generator,
        start=bind_start(deps),
        complete=bind_complete(deps),
        abort=bind_abort(deps),
        append=bind_append(deps, step_store=step_store),
    )

    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                ActionStep(
                    name="collect",
                    params={
                        "detector": f"{softioc}cam1",
                        "trigger_mode": "Internal",
                        "repetitions": 3,
                        "dwell": 0.05,
                    },
                ),
            ),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is True
    assert result.completed_count == 1

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT step_kind, payload
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1 AND payload->>'result' IS DISTINCT FROM 'in_flight'
            ORDER BY sampled_at, event_id
            """,
            procedure_id,
        )
    assert [r["step_kind"] for r in rows] == ["action"]
    payload = rows[0]["payload"]
    assert payload["name"] == "collect"
    assert payload["result"] == "ok"
    result_data = payload["result_data"]
    assert result_data["trigger_mode"] == "Internal"
    assert result_data["repetitions_requested"] == 3

    # Side-effects landed on the real softIOC PVs.
    async with control_port_reuse(softioc) as port:
        trigger_mode = await port.read(f"{softioc}cam1:TriggerMode")
        acquire_time = await port.read(f"{softioc}cam1:AcquireTime")
        num_images = await port.read(f"{softioc}cam1:NumImages")
        assert trigger_mode.value == "Internal"
        assert acquire_time.value == pytest.approx(0.05)
        assert num_images.value == 3


@pytest.mark.integration
async def test_conductor_runs_discrete_action_walks_axis_with_per_point_collects(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """`discrete` writes the axis at each of three points + runs a collect cycle."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0200")
    started_event_id = UUID("01900000-0000-7000-8000-0000020d0201")
    logbook_id = UUID("01900000-0000-7000-8000-0000020d0202")
    open_event_id = UUID("01900000-0000-7000-8000-0000020d0203")
    discrete_marker_id = UUID("01900000-0000-7000-8000-0000020d0204")
    discrete_step_id = UUID("01900000-0000-7000-8000-0000020d0205")
    completed_event_id = UUID("01900000-0000-7000-8000-0000020d0206")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            discrete_marker_id,
            discrete_step_id,
            completed_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    control_port = EpicsCaControlPort()
    conductor = _build_conductor(
        deps.event_store,
        db_pool,
        control_port,
        clock=deps.clock,
        id_generator=deps.id_generator,
        start=bind_start(deps),
        complete=bind_complete(deps),
        abort=bind_abort(deps),
        append=bind_append(deps, step_store=step_store),
    )

    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                ActionStep(
                    name="discrete",
                    params={
                        "detector": f"{softioc}cam1",
                        "trigger_mode": "Internal",
                        "axis": f"{softioc}double_value",
                        "points": (1.0, 2.0, 3.0),
                        "dwell": 0.05,
                    },
                ),
            ),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is True
    assert result.completed_count == 1

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT payload
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1 AND payload->>'result' IS DISTINCT FROM 'in_flight'
            """,
            procedure_id,
        )
    payload = rows[0]["payload"]
    assert payload["name"] == "discrete"
    assert payload["result"] == "ok"
    result_data = payload["result_data"]
    assert result_data["axis"] == f"{softioc}double_value"
    assert result_data["points_visited"] == 3
    assert [entry["point"] for entry in result_data["per_point_results"]] == [1.0, 2.0, 3.0]

    async with control_port_reuse(softioc) as port:
        axis_final = await port.read(f"{softioc}double_value")
        assert axis_final.value == pytest.approx(3.0)


@pytest.mark.integration
async def test_conductor_runs_continuous_action_with_axis_sweep_against_softioc(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """`continuous` arms the detector, sweeps the axis from start to stop."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0300")
    started_event_id = UUID("01900000-0000-7000-8000-0000020d0301")
    logbook_id = UUID("01900000-0000-7000-8000-0000020d0302")
    open_event_id = UUID("01900000-0000-7000-8000-0000020d0303")
    continuous_marker_id = UUID("01900000-0000-7000-8000-0000020d0304")
    continuous_step_id = UUID("01900000-0000-7000-8000-0000020d0305")
    completed_event_id = UUID("01900000-0000-7000-8000-0000020d0306")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            continuous_marker_id,
            continuous_step_id,
            completed_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    control_port = EpicsCaControlPort()
    conductor = _build_conductor(
        deps.event_store,
        db_pool,
        control_port,
        clock=deps.clock,
        id_generator=deps.id_generator,
        start=bind_start(deps),
        complete=bind_complete(deps),
        abort=bind_abort(deps),
        append=bind_append(deps, step_store=step_store),
    )

    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                ActionStep(
                    name="continuous",
                    params={
                        "detector": f"{softioc}cam1",
                        "trigger_mode": "Internal",
                        "axis": f"{softioc}double_value",
                        "start": 0.0,
                        "stop": 10.0,
                        "repetitions": 5,
                        "dwell": 0.05,
                    },
                ),
            ),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is True
    assert result.completed_count == 1

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT payload
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1 AND payload->>'result' IS DISTINCT FROM 'in_flight'
            """,
            procedure_id,
        )
    payload = rows[0]["payload"]
    assert payload["name"] == "continuous"
    assert payload["result"] == "ok"
    result_data = payload["result_data"]
    assert result_data["axis"] == f"{softioc}double_value"
    assert result_data["axis_start_requested"] == 0.0
    assert result_data["axis_stop_requested"] == 10.0
    assert result_data["axis_final_actual"] == pytest.approx(10.0)
    assert result_data["repetitions_requested"] == 5


class control_port_reuse:  # noqa: N801
    """Async-context manager that opens a fresh `EpicsCaControlPort` for assertions.

    The Conductor's own port is `aclose()`d after `conduct()` returns;
    readback assertions against PVs the body just wrote need a NEW port.
    Wrapping with `async with` so the assertion block closes the port
    deterministically.
    """

    def __init__(self, _softioc_prefix: str) -> None:
        self._port = EpicsCaControlPort()

    async def __aenter__(self) -> EpicsCaControlPort:
        return self._port

    async def __aexit__(self, *_: object) -> None:
        await self._port.aclose()
