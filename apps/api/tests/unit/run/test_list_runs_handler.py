"""Unit tests for the `list_runs` handler. Pool-less."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.projection import InvalidCursorError, encode_cursor
from cora.run.features.list_runs import ListRuns, bind
from tests.unit._helpers import build_deps

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_NOW = datetime(2026, 5, 13, 14, 0, 0, tzinfo=UTC)


@pytest.mark.unit
async def test_handler_returns_empty_page_when_no_pool() -> None:
    handler = bind(build_deps())
    page = await handler(
        ListRuns(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    handler = bind(build_deps(deny=True))
    with pytest.raises(Exception, match="denied for test"):
        await handler(
            ListRuns(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_cursor_for_garbage() -> None:
    handler = bind(build_deps())
    with pytest.raises(InvalidCursorError):
        await handler(
            ListRuns(cursor="not-a-real-cursor"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_accepts_well_formed_cursor() -> None:
    cursor = encode_cursor(
        created_at=_NOW,
        item_id=UUID("01900000-0000-7000-8000-000000000001"),
    )
    handler = bind(build_deps())
    page = await handler(
        ListRuns(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_accepts_combined_filters() -> None:
    handler = bind(build_deps())
    page = await handler(
        ListRuns(
            status="Running",
            plan_id=uuid4(),
            campaign_id=uuid4(),
            conduct_mode="Recorded",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.unit
async def test_handler_accepts_conduct_mode_filter() -> None:
    handler = bind(build_deps())
    page = await handler(
        ListRuns(conduct_mode="Recorded"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
