"""Outcome dataclass + InMemoryOutcomeStore tests.

Mirrors `test_procedure_diagnostic.py` (per-category writer port). The
PostgresOutcomeStore lives in integration tests; the in-memory adapter is
tested here for row shape + at-least-once dedup semantics. The Outcome entry
records the measured values (the y) a steered pass produced, for RESUME.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    InMemoryOutcomeStore,
    Outcome,
)

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)


def _row(
    *,
    event_id: UUID | None = None,
    iteration_index: int = 0,
    point: dict[str, object] | None = None,
    measurements: list[dict[str, object]] | None = None,
    succeeded: bool = True,
    actuation_kind: str | None = "Physical",
) -> Outcome:
    return Outcome(
        event_id=event_id or uuid4(),
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        iteration_index=iteration_index,
        point=point or {"energy": 8.0},
        measurements=measurements
        or [{"name": "flux", "value": 12.5, "kind": "Scalar", "quality": "Good", "units": None}],
        succeeded=succeeded,
        actuation_kind=actuation_kind,
        sampled_at=_NOW,
        occurred_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
    )


@pytest.mark.unit
def test_outcome_row_is_a_frozen_dataclass() -> None:
    row = _row()
    with pytest.raises(Exception):  # noqa: B017  # dataclass FrozenInstanceError
        row.succeeded = False  # type: ignore[misc]


@pytest.mark.unit
def test_outcome_row_carries_measurements_the_brain_fit() -> None:
    row = _row(
        measurements=[
            {"name": "flux", "value": 9.0, "kind": "Scalar", "quality": "Good", "units": None},
            {"name": "roi", "value": 3.2, "kind": "Scalar", "quality": "Good", "units": "mm"},
        ]
    )
    assert row.measurements[0]["value"] == 9.0
    assert row.measurements[1]["name"] == "roi"


@pytest.mark.unit
def test_outcome_row_is_self_describing_with_its_measured_point() -> None:
    """The row carries the coordinate it measured at (the x), so resume needs no join."""
    row = _row(point={"energy": 9.5, "angle": 1.2})
    assert row.point == {"energy": 9.5, "angle": 1.2}


@pytest.mark.unit
def test_outcome_row_links_to_its_iteration_and_carries_provenance() -> None:
    row = _row(iteration_index=7, actuation_kind="Simulated", succeeded=False)
    assert row.iteration_index == 7
    assert row.actuation_kind == "Simulated"
    assert row.succeeded is False


# ---------- InMemoryOutcomeStore ----------


@pytest.mark.unit
async def test_inmemory_outcome_store_appends_single_row() -> None:
    store = InMemoryOutcomeStore()
    row = _row()
    await store.append([row])
    assert store.all() == [row]


@pytest.mark.unit
async def test_inmemory_outcome_store_appends_batch_preserving_ids() -> None:
    store = InMemoryOutcomeStore()
    rows = [_row(iteration_index=i) for i in range(5)]
    await store.append(rows)
    assert {r.event_id for r in store.all()} == {r.event_id for r in rows}


@pytest.mark.unit
async def test_inmemory_outcome_store_dedups_by_event_id_first_wins() -> None:
    store = InMemoryOutcomeStore()
    eid = uuid4()
    first = _row(event_id=eid, iteration_index=0)
    second = _row(event_id=eid, iteration_index=1)  # same id, different body
    await store.append([first])
    await store.append([second])
    assert len(store.all()) == 1
    assert store.all()[0].iteration_index == 0  # first wins


@pytest.mark.unit
async def test_inmemory_outcome_store_handles_empty_batch_as_noop() -> None:
    store = InMemoryOutcomeStore()
    await store.append([])
    assert store.all() == []
