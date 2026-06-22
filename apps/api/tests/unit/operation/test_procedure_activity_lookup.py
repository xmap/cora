"""Unit tests for the ProcedureActivityLookup read port (in-memory stub).

The stub is the contract the PostgresProcedureActivityLookup adapter
mirrors: an unseeded procedure reads a None recency (cannot-tell, the
watcher keeps the status timestamp as the clock), and a seeded one
returns the newest `recorded_at`, not insertion order. The Postgres
parity is covered in the integration suite.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.operation.ports import InMemoryProcedureActivityLookup

_PROC = uuid4()
_T0 = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return _T0 + timedelta(seconds=seconds)


@pytest.mark.unit
async def test_recency_returns_none_when_procedure_never_logged_activity() -> None:
    """An unseeded procedure is the cannot-tell case: the watcher keeps the
    status timestamp as the staleness clock rather than folding."""
    lookup = InMemoryProcedureActivityLookup()
    recency = await lookup.read_procedure_activity_recency(procedure_id=_PROC)
    assert recency.latest_recorded_at is None


@pytest.mark.unit
async def test_recency_returns_newest_recorded_at_not_insertion_order() -> None:
    """Recency keys on max(recorded_at), independent of registration order."""
    lookup = InMemoryProcedureActivityLookup()
    lookup.register(procedure_id=_PROC, recorded_at=_at(30))
    lookup.register(procedure_id=_PROC, recorded_at=_at(10))
    lookup.register(procedure_id=_PROC, recorded_at=_at(20))
    recency = await lookup.read_procedure_activity_recency(procedure_id=_PROC)
    assert recency.latest_recorded_at == _at(30)


@pytest.mark.unit
async def test_recency_is_scoped_per_procedure() -> None:
    """One procedure's activity does not leak into another's recency."""
    other = uuid4()
    lookup = InMemoryProcedureActivityLookup()
    lookup.register(procedure_id=_PROC, recorded_at=_at(5))
    recency = await lookup.read_procedure_activity_recency(procedure_id=other)
    assert recency.latest_recorded_at is None
