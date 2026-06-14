"""Application-handler tests for `list_procedure_iterations` query slice.

Without a Postgres pool the handler short-circuits to an empty list;
real query behavior is in the integration suite.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.errors import UnauthorizedError
from cora.operation.features import list_procedure_iterations
from cora.operation.features.list_procedure_iterations import ListProcedureIterations
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_handler_returns_empty_list_when_pool_is_none() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_procedure_iterations.bind(deps)
    page = await handler(
        ListProcedureIterations(procedure_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW, deny=True)
    handler = list_procedure_iterations.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListProcedureIterations(procedure_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
