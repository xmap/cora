"""End-to-end integration test: `CaptureBaselineReader` + softIOC + Postgres.

Mirrors `test_acquisitions_against_softioc_postgres.py`'s shape: a real
`EpicsCaControlPort` behind a `ControlPortRegistry`, real handlers bound
against `PostgresEventStore` + `PostgresObservationStore`. The 2-BM IOCs
are down, so the soft-IOC's own `enum_value` PV (`mbbo`, labels
`off`/`on`/`fault`) is the closest offline proxy for the real
`2bmb:TomoScan:*` scan-configuration enums this module exists to record,
per the soft-IOC harness's own docstring.

Covers the mandatory case from the slice's testing note: a categorical
reading round-trips its label unchanged through the real EPICS wire
decode (`EpicsCaControlPort`'s DBR_ENUM -> `Measurement(kind=
"Categorical")` collapse), not just through a scripted fake.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._capture_baseline_reader import CaptureBaselineReader
from cora.infrastructure.event_envelope import to_new_event
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.ports.control_address import EpicsPvAddress
from cora.run.aggregates.run import PostgresObservationStore
from cora.run.aggregates.run.events import RunStarted, event_type_name, to_payload
from cora.run.features.append_observations import bind as bind_append
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000006f7099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000006f70aa")


async def _seed_run_started(deps_event_store: object, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="Softioc-baseline-test Run",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await deps_event_store.append(  # type: ignore[attr-defined]
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.integration
async def test_categorical_baseline_reading_round_trips_label_through_real_epics_decode(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """A categorical (`enum_value`, DBR_ENUM) and a numeric (`double_value`,
    DBR_DOUBLE) baseline PV, read through the real `EpicsCaControlPort`,
    land as one retrievable genesis snapshot: the enum row carries the
    substrate's own label unchanged in `categorical_value`, the numeric
    row carries its coerced float in `value`, and neither leaks into the
    other's column."""
    run_id = UUID("01900000-0000-7000-8000-0000006f7001")
    logbook_id = UUID("01900000-0000-7000-8000-0000006f7002")
    open_event_id = UUID("01900000-0000-7000-8000-0000006f7003")

    control_port = ControlPortRegistry()
    control_port.register_substrate_port(softioc, EpicsCaControlPort(), "epics_ca")

    # Deterministic substrate state: write the enum to its "fault" label
    # and the double to a known value before the reader ever sees them.
    setup_port = EpicsCaControlPort()
    try:
        await setup_port.write(EpicsPvAddress(f"{softioc}enum_value"), "fault", wait=True)
        await setup_port.write(EpicsPvAddress(f"{softioc}double_value"), 3.5, wait=True)
    finally:
        await setup_port.aclose()

    deps = build_postgres_deps(
        db_pool, now=_NOW, ids=[logbook_id, open_event_id, *(uuid4() for _ in range(10))]
    )
    observation_store = PostgresObservationStore(db_pool)
    await _seed_run_started(deps.event_store, run_id)

    handler = bind_append(deps, observation_store=observation_store)
    reader = CaptureBaselineReader(
        deps=deps,
        control_port=control_port,
        baseline_pvs={
            "2bmb-tomoscan": {
                "ScanType": f"{softioc}enum_value",
                "ExposureTime": f"{softioc}double_value",
            }
        },
        append_observations=handler,
        principal_id=_PRINCIPAL_ID,
    )

    try:
        await reader.read("2bmb-tomoscan", run_id)
    finally:
        await control_port.aclose()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT channel_name, value, categorical_value, sampling_procedure
            FROM entries_run_observations
            WHERE run_id = $1
            """,
            run_id,
        )
    by_channel = {r["channel_name"]: r for r in rows}
    assert set(by_channel) == {"ScanType", "ExposureTime"}

    scan_type = by_channel["ScanType"]
    assert scan_type["value"] is None
    assert scan_type["categorical_value"] == "fault"
    assert scan_type["sampling_procedure"] == "baseline"

    exposure_time = by_channel["ExposureTime"]
    assert exposure_time["value"] == pytest.approx(3.5)
    assert exposure_time["categorical_value"] is None
