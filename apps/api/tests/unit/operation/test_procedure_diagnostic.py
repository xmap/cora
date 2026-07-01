"""Diagnostic dataclass + InMemoryDiagnosticStore tests.

Mirrors `test_procedure_activity.py` (per-category writer port). The
PostgresDiagnosticStore lives in integration tests; the in-memory adapter is
tested here for row shape + at-least-once dedup semantics.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    Diagnostic,
    InMemoryDiagnosticStore,
)

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)


def _row(
    *,
    event_id: UUID | None = None,
    iteration_index: int = 0,
    payload: dict[str, object] | None = None,
) -> Diagnostic:
    return Diagnostic(
        event_id=event_id or uuid4(),
        procedure_id=uuid4(),
        logbook_id=uuid4(),
        iteration_index=iteration_index,
        model_ref="botorch",
        payload=payload or {"lengthscale_energy": 0.81, "noise": 0.005, "acquisition_value": 0.12},
        sampled_at=_NOW,
        occurred_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
    )


@pytest.mark.unit
def test_diagnostic_row_is_a_frozen_dataclass() -> None:
    row = _row()
    with pytest.raises(Exception):  # noqa: B017  # dataclass FrozenInstanceError
        row.model_ref = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_diagnostic_row_carries_fit_scalars_in_payload() -> None:
    row = _row(
        payload={
            "lengthscale_x": 0.9,
            "lengthscale_y": 1.2,
            "noise": 0.01,
            "acquisition_value": 0.3,
        }
    )
    assert row.payload["lengthscale_x"] == 0.9
    assert row.payload["acquisition_value"] == 0.3


@pytest.mark.unit
def test_diagnostic_row_links_to_its_iteration() -> None:
    row = _row(iteration_index=7)
    assert row.iteration_index == 7
    assert row.model_ref == "botorch"


# ---------- InMemoryDiagnosticStore ----------


@pytest.mark.unit
async def test_inmemory_diagnostic_store_appends_single_row() -> None:
    store = InMemoryDiagnosticStore()
    row = _row()
    await store.append([row])
    assert store.all() == [row]


@pytest.mark.unit
async def test_inmemory_diagnostic_store_appends_batch_preserving_ids() -> None:
    store = InMemoryDiagnosticStore()
    rows = [_row(iteration_index=i) for i in range(5)]
    await store.append(rows)
    assert {r.event_id for r in store.all()} == {r.event_id for r in rows}


@pytest.mark.unit
async def test_inmemory_diagnostic_store_dedups_by_event_id_first_wins() -> None:
    store = InMemoryDiagnosticStore()
    eid = uuid4()
    first = _row(event_id=eid, iteration_index=0)
    second = _row(event_id=eid, iteration_index=1)  # same id, different body
    await store.append([first])
    await store.append([second])
    assert len(store.all()) == 1
    assert store.all()[0].iteration_index == 0  # first wins


@pytest.mark.unit
async def test_inmemory_diagnostic_store_handles_empty_batch_as_noop() -> None:
    store = InMemoryDiagnosticStore()
    await store.append([])
    assert store.all() == []
