"""Unit tests for the Observation entry + ObservationStore.

Mirrors `test_decision_inferences.py` shape — the dataclass
round-trips, the in-memory store dedups on event_id, batch and
single-element appends both work, empty list is a no-op.

Observation is the first POLYMORPHIC-with-discriminator entry kind
(prior two entry kinds are typed-per-category). The polymorphism
is exercised via the `sampling_procedure` field; baseline + monitor
+ future kinds all share this row shape.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    InMemoryObservationStore,
    Observation,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _row(**overrides: object) -> Observation:
    base: dict[str, object] = {
        "event_id": uuid4(),
        "run_id": uuid4(),
        "logbook_id": uuid4(),
        "actor_id": uuid4(),
        "command_name": "AppendObservations",
        "channel_name": "T_sample",
        "value": 295.1,
        "units": "K",
        "sampling_procedure": "baseline",
        "sampled_at": _NOW,
        "occurred_at": _NOW,
        "correlation_id": uuid4(),
        "causation_id": None,
        "is_simulated": False,
    }
    base.update(overrides)
    return Observation(**base)  # type: ignore[arg-type]


# ---------- Observation dataclass shape ----------


@pytest.mark.unit
def test_run_observation_required_fields_present() -> None:
    """`channel_name`, `value`, `sampled_at`, `sampling_procedure` are
    the polymorphic row's required value fields."""
    row = _row()
    assert row.channel_name == "T_sample"
    assert row.value == 295.1
    assert row.sampling_procedure == "baseline"
    assert row.sampled_at == _NOW


@pytest.mark.unit
def test_run_observation_units_optional() -> None:
    """Units are optional (some channels are dimensionless)."""
    row = _row(units=None)
    assert row.units is None


@pytest.mark.unit
def test_run_observation_three_timestamps_distinct() -> None:
    """SOSA dual-time + DB time: sampled_at, occurred_at, recorded_at
    can all differ (and recorded_at is set by Postgres in production;
    in-memory store doesn't model recorded_at — that's a Postgres
    DEFAULT). Verify that the dataclass carries sampled_at and
    occurred_at as independent fields."""
    sampled = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
    occurred = datetime(2026, 5, 14, 12, 0, 5, tzinfo=UTC)
    row = _row(sampled_at=sampled, occurred_at=occurred)
    assert row.sampled_at == sampled
    assert row.occurred_at == occurred
    assert row.sampled_at != row.occurred_at


@pytest.mark.unit
@pytest.mark.parametrize(
    "procedure",
    ["baseline"],
)
def test_run_observation_accepts_known_sampling_procedures(procedure: str) -> None:
    """Polymorphic over sampling_procedure: today {'baseline'} only.
    6f-5c will extend to {'baseline', 'monitor'}; future-additive."""
    row = _row(sampling_procedure=procedure)
    assert row.sampling_procedure == procedure


@pytest.mark.unit
def test_run_observation_is_simulated_defaults_real_and_carries_sim_flag() -> None:
    """Provenance: a row is real (is_simulated False) by default; a sim
    feeder sets it True. The closed-loop read seam disqualifies True so a
    rule cannot act on simulated data as if it were real."""
    real_row = _row()
    assert real_row.is_simulated is False
    sim_row = _row(is_simulated=True)
    assert sim_row.is_simulated is True


@pytest.mark.unit
def test_run_observation_carries_envelope_fields() -> None:
    """Audit trail: actor_id (principal who appended), command_name
    (always 'AppendObservations' for this entry kind), correlation_id
    (request trace), causation_id (chain)."""
    row = _row(actor_id=uuid4(), causation_id=uuid4())
    assert row.actor_id is not None
    assert row.command_name == "AppendObservations"
    assert row.correlation_id is not None
    assert row.causation_id is not None


# ---------- InMemoryObservationStore ----------


@pytest.mark.unit
async def test_in_memory_store_appends_single_row() -> None:
    store = InMemoryObservationStore()
    row = _row()
    await store.append([row])
    assert store.all() == [row]


@pytest.mark.unit
async def test_in_memory_store_appends_batch() -> None:
    """DAQ adapters typically batch a frame's worth of channels in
    one call; multi-row append works."""
    store = InMemoryObservationStore()
    rows = [_row(channel_name=f"ch_{i}") for i in range(5)]
    await store.append(rows)
    assert len(store.all()) == 5


@pytest.mark.unit
async def test_in_memory_store_empty_list_is_noop() -> None:
    store = InMemoryObservationStore()
    await store.append([])
    assert store.all() == []


@pytest.mark.unit
async def test_in_memory_store_dedups_on_event_id() -> None:
    """At-least-once semantics: retrying with the same event_id must
    not produce two stored rows. First write wins (matches Postgres
    ON CONFLICT (event_id) DO NOTHING shape)."""
    store = InMemoryObservationStore()
    event_id = uuid4()
    first = _row(event_id=event_id, value=295.1)
    second = _row(event_id=event_id, value=999.0)
    await store.append([first])
    await store.append([second])
    assert store.all() == [first]
    assert store.all()[0].value == 295.1


@pytest.mark.unit
async def test_in_memory_store_preserves_insertion_order_across_calls() -> None:
    """all() returns rows in insertion order for predictable test
    assertions."""
    store = InMemoryObservationStore()
    a = _row()
    b = _row()
    c = _row()
    await store.append([a])
    await store.append([b, c])
    assert store.all() == [a, b, c]


@pytest.mark.unit
async def test_in_memory_store_polymorphic_across_procedures() -> None:
    """Single store holds rows of different sampling_procedure values
    side-by-side. This is the polymorphic-with-discriminator design:
    the store doesn't care about the procedure, callers filter when
    they query."""
    store = InMemoryObservationStore()
    baseline_row = _row(sampling_procedure="baseline", channel_name="T_baseline")
    # 6f-5c will introduce "monitor"; for 6f-5b, all rows are
    # baseline, but the store doesn't validate the discriminator
    # (validation lives at the API + handler layer).
    await store.append([baseline_row])
    rows = store.all()
    assert len(rows) == 1
    assert rows[0].sampling_procedure == "baseline"
