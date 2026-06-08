"""Application-handler tests for `list_cautions` query slice.

Without a Postgres pool the handler short-circuits to an empty page;
real query behavior is in the integration suite. These tests pin:

  - empty-page no-pool branch
  - authorize Deny -> UnauthorizedError
  - cursor decode roundtrip
  - filter pass-through (canonical list-typed `severities` /
    `statuses`; user-facing sentinel / ladder translation lives in
    the route + MCP tool and is covered by the contract tier)
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from cora.caution.errors import UnauthorizedError
from cora.caution.features import list_cautions
from cora.caution.features.list_cautions import ListCautions
from cora.infrastructure.ports import Allow
from cora.infrastructure.projection import encode_cursor
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAUTION_ID = UUID("01900000-0000-7000-8000-00000000c001")
_TARGET_ID = UUID("01900000-0000-7000-8000-00000000c002")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000c003"))


@pytest.mark.unit
async def test_handler_returns_empty_page_when_pool_is_none() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_accepts_canonical_filter_shape() -> None:
    """`ListCautions` carries canonical list-typed severities / statuses;
    the route/MCP-tool translate user-facing UX before calling here."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(
            target_kind="Asset",
            target_id=_TARGET_ID,
            category="Wear",
            severities=["Caution", "Warning"],
            statuses=["Active"],
            tag="hexapod",
            authored_by=_AUTHOR_ID,
            limit=20,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Pool is None: returns empty. The test pins the handler accepts the filter shape.
    assert page.items == []


@pytest.mark.unit
async def test_handler_default_query_uses_no_filters() -> None:
    """`ListCautions()` (no args) means "no filter" on every dimension.

    Important consequence of the Phase-2 cleanup that dropped the
    handler-tier `status` default-to-'Active' resolution: any direct
    caller (test, internal code, future saga) gets ALL statuses
    unless it explicitly passes `statuses=['Active']`. The 'Active'
    default is now a route + MCP-tool convention, NOT a query-
    dataclass behavior. See `cora.caution.features.list_cautions.query`
    docstring.
    """
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_cautions.bind(deps)
    query = ListCautions()
    assert query.statuses is None  # the assertion-of-record for this behavior
    assert query.severities is None
    page = await handler(
        query,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW, deny=True)
    handler = list_cautions.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListCautions(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_accepts_well_formed_cursor() -> None:
    cursor = encode_cursor(created_at=_NOW, item_id=_CAUTION_ID)
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_authorize_called_with_query_name_constant() -> None:
    """Pins the BOLA gating key: command_name == 'ListCautions'."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    authorize_mock = AsyncMock(return_value=Allow())
    authz_stub = SimpleNamespace(authorize=authorize_mock)
    object.__setattr__(deps, "authz", authz_stub)
    handler = list_cautions.bind(deps)
    await handler(
        ListCautions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    authorize_mock.assert_awaited_once()
    call = authorize_mock.await_args
    assert call is not None
    assert call.kwargs["command_name"] == "ListCautions"
