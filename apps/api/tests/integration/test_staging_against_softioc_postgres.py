"""Integration test: the `flats` staging body + Conductor + EpicsCaControlPort + Postgres.

Mirrors `test_acquisitions_against_softioc_postgres.py` for the sample-
staging composition `flats` (a `collect` cycle bracketed by an axis
save-and-restore). Proves the read-offcentre-collect-restore sequence
against real Channel Access framing: the axis is driven off its saved
position for the capture and restored afterwards, verified by re-reading
the PV with a fresh port.

`flats` lives in `cora.operation.staging`, not the scan-primitives module,
because it is a composition (collect + sample staging), not an acquisition
motion. See that module's docstring for the conduct variable-binding gap
this body stands in for.
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
from cora.operation.conductor import ActionStep, Conductor, InMemoryActionRegistry
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.start_procedure import bind as bind_start
from cora.operation.staging import flats
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 22, 9, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020f0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020f00aa")

_ACTION_REGISTRY = InMemoryActionRegistry({"flats": flats})


async def _seed_defined_procedure(deps_event_store: object, procedure_id: UUID) -> None:
    """Seed a single ProcedureRegistered event so the Procedure exists in Defined."""
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM staging smoke",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    stored = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=registered.occurred_at,
        event_id=UUID("01900000-0000-7000-8000-0000020f0001"),
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
async def test_conductor_runs_flats_action_retracts_then_restores_axis_against_softioc(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """`flats` reads the axis, drives off-centre by clearance, collects, restores."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020f0100")
    started_event_id = UUID("01900000-0000-7000-8000-0000020f0101")
    logbook_id = UUID("01900000-0000-7000-8000-0000020f0102")
    open_event_id = UUID("01900000-0000-7000-8000-0000020f0103")
    flats_marker_id = UUID("01900000-0000-7000-8000-0000020f0104")
    flats_step_id = UUID("01900000-0000-7000-8000-0000020f0105")
    completed_event_id = UUID("01900000-0000-7000-8000-0000020f0106")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            flats_marker_id,
            flats_step_id,
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
        action_registry=_ACTION_REGISTRY,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )

    try:
        # The aligned-centre position the body must read then restore to.
        await control_port.write(f"{softioc}double_value", 12.5, wait=True)
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                ActionStep(
                    name="flats",
                    params={
                        "detector": f"{softioc}cam1",
                        "trigger_mode": "Internal",
                        "axis": f"{softioc}double_value",
                        "clearance": 5.0,
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
            SELECT payload
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1 AND payload->>'result' IS DISTINCT FROM 'in_flight'
            """,
            procedure_id,
        )
    payload = rows[0]["payload"]
    assert payload["name"] == "flats"
    assert payload["result"] == "ok"
    result_data = payload["result_data"]
    assert result_data["axis"] == f"{softioc}double_value"
    assert result_data["saved_value"] == pytest.approx(12.5)
    assert result_data["offcenter_target"] == pytest.approx(17.5)
    assert result_data["collect"]["repetitions_requested"] == 3

    # The axis is back at the aligned centre the body saved (the restore landed).
    fresh_port = EpicsCaControlPort()
    try:
        axis_final = await fresh_port.read(f"{softioc}double_value")
        assert axis_final.value == pytest.approx(12.5)
    finally:
        await fresh_port.aclose()
