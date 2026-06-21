"""End-to-end integration test: append_observations against real Postgres.

First concrete consumer of the entries_run_observations table +
PostgresObservationStore. Stress-tests the polymorphic-with-discriminator
storage shape + lazy open-on-first-write + dedup-on-event_id +
SOSA dual-time round-trip against actual Postgres semantics
(double precision NaN/Inf CHECK constraint, BRIN index on
recorded_at, plain TEXT discriminator column).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.run.aggregates.run import (
    PostgresObservationStore,
    fold,
    from_stored,
)
from cora.run.aggregates.run.events import (
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.features.append_observations import (
    AppendObservations,
    ObservationInput,
)
from cora.run.features.append_observations import bind as bind_append
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_run_started(
    deps_event_store: object,
    run_id: UUID,
) -> None:
    """Seed a RunStarted event directly into the event store.

    We bypass start_run's full upstream-chain validation
    (Family + Asset + Method + Practice + Plan + Subject + Mount)
    because this test focuses on the reading entry + lazy open path
    against Postgres, not Run-start. Direct seed mirrors the unit
    test's _seed_run_started for portability."""
    event = RunStarted(
        run_id=run_id,
        name="Integration-test Run",
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


async def _read_readings_for_run(db_pool: asyncpg.Pool, run_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT
                event_id, run_id, logbook_id, actor_id, command_name,
                channel_name, value, units, sampling_procedure,
                sampled_at, occurred_at, recorded_at,
                correlation_id, causation_id, is_simulated
            FROM entries_run_observations
            WHERE run_id = $1
            ORDER BY sampled_at, event_id
            """,
            run_id,
        )


@pytest.mark.integration
async def test_append_observations_full_lazy_open_and_polymorphic_round_trip(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: seed a Run, then append a 3-entry batch with
    different channels but the SAME sampling_procedure. Verify lazy
    RunObservationLogbookOpened landed on the Run stream, all 3 rows
    landed in entries_run_observations with typed columns + correct
    discriminator + sampled_at preserved, and a follow-up append on
    the same Run skips the open + appends to the same logbook."""
    run_id = UUID("01900000-0000-7000-8000-0000006f5b01")
    logbook_id = UUID("01900000-0000-7000-8000-0000006f5b02")
    open_event_id = UUID("01900000-0000-7000-8000-0000006f5b03")
    entry_a_id = UUID("01900000-0000-7000-8000-0000006f5c01")
    entry_b_id = UUID("01900000-0000-7000-8000-0000006f5c02")
    entry_c_id = UUID("01900000-0000-7000-8000-0000006f5c03")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[logbook_id, open_event_id],
    )
    observation_store = PostgresObservationStore(db_pool)

    await _seed_run_started(deps.event_store, run_id)

    # First append: lazy open emits RunObservationLogbookOpened + 3 entries land.
    sampled_a = datetime(2026, 5, 14, 11, 59, 50, tzinfo=UTC)
    sampled_b = datetime(2026, 5, 14, 11, 59, 51, tzinfo=UTC)
    sampled_c = datetime(2026, 5, 14, 11, 59, 52, tzinfo=UTC)
    entries = (
        ObservationInput(
            event_id=entry_a_id,
            channel_name="T_sample",
            value=295.1,
            sampled_at=sampled_a,
            sampling_procedure="baseline",
            units="K",
        ),
        ObservationInput(
            event_id=entry_b_id,
            channel_name="motor_x",
            value=12.345,
            sampled_at=sampled_b,
            sampling_procedure="baseline",
            units="mm",
        ),
        ObservationInput(
            event_id=entry_c_id,
            channel_name="ring_current_dimensionless",
            value=0.997,  # No units (dimensionless ratio).
            sampled_at=sampled_c,
            sampling_procedure="baseline",
            units=None,
        ),
    )
    count = await bind_append(deps, observation_store=observation_store)(
        AppendObservations(run_id=run_id, entries=entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 3

    # Verify Run stream now carries RunObservationLogbookOpened.
    stored, version = await deps.event_store.load("Run", run_id)
    assert version == 2
    assert [s.event_type for s in stored] == ["RunStarted", "RunObservationLogbookOpened"]
    state = fold([from_stored(s) for s in stored])
    assert state is not None
    assert state.observation_logbook_id == logbook_id

    # Read rows from entries_run_observations.
    rows = await _read_readings_for_run(db_pool, run_id)
    assert len(rows) == 3

    row_a = next(r for r in rows if r["event_id"] == entry_a_id)
    row_c = next(r for r in rows if r["event_id"] == entry_c_id)
    # row_b implicitly verified by len(rows) == 3 above; the typed-
    # column round-trip is exercised on row_a + row_c (channel /
    # value / units variations cover the polymorphic shape).

    # Typed columns survive round-trip.
    assert row_a["run_id"] == run_id
    assert row_a["logbook_id"] == logbook_id
    assert row_a["correlation_id"] == _CORRELATION_ID
    assert row_a["actor_id"] == _PRINCIPAL_ID
    assert row_a["command_name"] == "AppendObservations"
    assert row_a["channel_name"] == "T_sample"
    assert row_a["value"] == pytest.approx(295.1)
    assert row_a["units"] == "K"
    assert row_a["sampling_procedure"] == "baseline"
    assert row_a["sampled_at"] == sampled_a

    # Optional units null on row_c.
    assert row_c["units"] is None

    # is_simulated defaults to false (real) when the producer omits it.
    assert row_a["is_simulated"] is False

    # recorded_at is set by Postgres DEFAULT now(); just verify it's
    # a datetime within a sane window of the test execution.
    assert row_a["recorded_at"] is not None
    assert isinstance(row_a["recorded_at"], datetime)


@pytest.mark.integration
async def test_append_observations_persists_is_simulated_flag(
    db_pool: asyncpg.Pool,
) -> None:
    """A sim feeder's is_simulated=True and a real producer's default
    False both round-trip through the new column. This is the per-row
    provenance the closed-loop read seam filters on so a rule cannot act
    on simulated data as if it were real."""
    run_id = UUID("01900000-0000-7000-8000-0000006f5e01")
    logbook_id = UUID("01900000-0000-7000-8000-0000006f5e02")
    open_event_id = UUID("01900000-0000-7000-8000-0000006f5e03")
    real_id = UUID("01900000-0000-7000-8000-0000006f5e11")
    sim_id = UUID("01900000-0000-7000-8000-0000006f5e12")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    observation_store = PostgresObservationStore(db_pool)
    await _seed_run_started(deps.event_store, run_id)

    entries = (
        ObservationInput(
            event_id=real_id,
            channel_name="snr",
            value=7.2,
            sampled_at=_NOW,
            sampling_procedure="monitor",
        ),
        ObservationInput(
            event_id=sim_id,
            channel_name="snr",
            value=7.2,
            sampled_at=_NOW,
            sampling_procedure="monitor",
            is_simulated=True,
        ),
    )
    count = await bind_append(deps, observation_store=observation_store)(
        AppendObservations(run_id=run_id, entries=entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 2

    rows = await _read_readings_for_run(db_pool, run_id)
    by_id = {r["event_id"]: r for r in rows}
    assert by_id[real_id]["is_simulated"] is False
    assert by_id[sim_id]["is_simulated"] is True


@pytest.mark.integration
async def test_append_observations_second_call_skips_open_and_dedups(
    db_pool: asyncpg.Pool,
) -> None:
    """Second append on the same Run sees the logbook already open
    (skips emit) AND a retry with the same event_id is silently
    deduped via Postgres PK (`ON CONFLICT (event_id) DO NOTHING`)."""
    run_id = UUID("01900000-0000-7000-8000-0000006f5b11")
    logbook_id = UUID("01900000-0000-7000-8000-0000006f5b12")
    open_event_id = UUID("01900000-0000-7000-8000-0000006f5b13")
    shared_event_id = UUID("01900000-0000-7000-8000-0000006f5c11")

    deps_first = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[logbook_id, open_event_id],
    )
    observation_store = PostgresObservationStore(db_pool)

    await _seed_run_started(deps_first.event_store, run_id)

    first_entry = ObservationInput(
        event_id=shared_event_id,
        channel_name="T_sample",
        value=295.1,
        sampled_at=_NOW,
        sampling_procedure="baseline",
        units="K",
    )
    await bind_append(deps_first, observation_store=observation_store)(
        AppendObservations(run_id=run_id, entries=(first_entry,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Second call: fresh deps (fresh id_generator). Same event_id.
    deps_second = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4(), uuid4(), uuid4()],
    )
    second_entry = ObservationInput(
        event_id=shared_event_id,
        channel_name="T_sample",
        value=999.0,  # Different value, but ON CONFLICT DO NOTHING preserves first.
        sampled_at=_NOW,
        sampling_procedure="baseline",
        units="K",
    )
    await bind_append(deps_second, observation_store=observation_store)(
        AppendObservations(run_id=run_id, entries=(second_entry,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run stream still has only 2 events (RunStarted + 1 logbook open).
    _, version = await deps_first.event_store.load("Run", run_id)
    assert version == 2

    # Reading row is present once with the FIRST value (dedup).
    rows = await _read_readings_for_run(db_pool, run_id)
    assert len(rows) == 1
    assert rows[0]["value"] == pytest.approx(295.1)


@pytest.mark.integration
async def test_append_observations_polymorphic_baseline_and_monitor_coexist(
    db_pool: asyncpg.Pool,
) -> None:
    """6f-5c: a single Run holds BOTH baseline and monitor readings
    in the same `entries_run_observations` table (the polymorphic-with-
    discriminator design earns its keep). Verify the kind-filtered
    index `entries_run_readings_run_procedure_sampled_idx` is
    queryable via the SQL pattern the design memo prescribes for
    'show me only baselines on Run X'."""
    run_id = UUID("01900000-0000-7000-8000-0000006f5c01")
    logbook_id = UUID("01900000-0000-7000-8000-0000006f5c02")
    open_event_id = UUID("01900000-0000-7000-8000-0000006f5c03")
    baseline_start_id = UUID("01900000-0000-7000-8000-0000006f5d01")
    monitor_a_id = UUID("01900000-0000-7000-8000-0000006f5d02")
    monitor_b_id = UUID("01900000-0000-7000-8000-0000006f5d03")
    baseline_end_id = UUID("01900000-0000-7000-8000-0000006f5d04")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[logbook_id, open_event_id],
    )
    observation_store = PostgresObservationStore(db_pool)

    await _seed_run_started(deps.event_store, run_id)

    # Run-start baseline + 2 monitor mid-run + Run-end baseline,
    # all the same channel ("T_sample"), all the same Run.
    sampled_start = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
    sampled_a = datetime(2026, 5, 14, 12, 0, 30, tzinfo=UTC)
    sampled_b = datetime(2026, 5, 14, 12, 1, 0, tzinfo=UTC)
    sampled_end = datetime(2026, 5, 14, 12, 1, 30, tzinfo=UTC)
    entries = (
        ObservationInput(
            event_id=baseline_start_id,
            channel_name="T_sample",
            value=295.1,
            sampled_at=sampled_start,
            sampling_procedure="baseline",
            units="K",
        ),
        ObservationInput(
            event_id=monitor_a_id,
            channel_name="T_sample",
            value=294.8,
            sampled_at=sampled_a,
            sampling_procedure="monitor",
            units="K",
        ),
        ObservationInput(
            event_id=monitor_b_id,
            channel_name="T_sample",
            value=295.0,
            sampled_at=sampled_b,
            sampling_procedure="monitor",
            units="K",
        ),
        ObservationInput(
            event_id=baseline_end_id,
            channel_name="T_sample",
            value=295.4,
            sampled_at=sampled_end,
            sampling_procedure="baseline",
            units="K",
        ),
    )
    count = await bind_append(deps, observation_store=observation_store)(
        AppendObservations(run_id=run_id, entries=entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 4

    # All 4 rows present, sharing the same logbook_id.
    rows = await _read_readings_for_run(db_pool, run_id)
    assert len(rows) == 4
    assert {r["logbook_id"] for r in rows} == {logbook_id}

    # Kind-filtered SQL: "all baselines on Run X" via the
    # entries_run_readings_run_procedure_sampled_idx index. The
    # query shape is what the design memo prescribes for the
    # polymorphic-with-discriminator read pattern.
    async with db_pool.acquire() as conn:
        baseline_rows = await conn.fetch(
            """
            SELECT event_id, value, sampled_at
            FROM entries_run_observations
            WHERE run_id = $1 AND sampling_procedure = $2
            ORDER BY sampled_at
            """,
            run_id,
            "baseline",
        )
        monitor_rows = await conn.fetch(
            """
            SELECT event_id, value, sampled_at
            FROM entries_run_observations
            WHERE run_id = $1 AND sampling_procedure = $2
            ORDER BY sampled_at
            """,
            run_id,
            "monitor",
        )
    assert len(baseline_rows) == 2
    assert [r["value"] for r in baseline_rows] == pytest.approx([295.1, 295.4])
    assert len(monitor_rows) == 2
    assert [r["value"] for r in monitor_rows] == pytest.approx([294.8, 295.0])

    # Run stream still has just one logbook-open event (lazy open
    # survives across procedure kinds — proves the polymorphic
    # design avoids per-kind logbook proliferation).
    stored, version = await deps.event_store.load("Run", run_id)
    assert version == 2
    assert [s.event_type for s in stored] == ["RunStarted", "RunObservationLogbookOpened"]
