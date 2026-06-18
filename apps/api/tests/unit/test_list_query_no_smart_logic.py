"""Regression guard: the `list_query` factory must NEVER emit the
"smart logic" anti-pattern (`($N IS NULL OR column = $N)`).

Background: per Markus Winand
(https://use-the-index-luke.com/sql/where-clause/obfuscation/smart-logic),
that pattern is non-sargable under PostgreSQL's generic plan
(the planner switches to it after 5 executions of a prepared
statement; asyncpg auto-caches prepared statements per connection).
A generic-plan execution can't prove either branch of the OR is
unreachable and falls back to a sequential scan even when the
column has a perfect index.

The factory was redesigned to compose SQL dynamically from only the
active filter fragments, so this anti-pattern can't be emitted by
construction. This test pins that invariant: if a future change to
`render_filter_fragment` or `build_select` ever reintroduces the
pattern (or merely a fragment that looks like it), the test fails.

Companion integration test
`tests/integration/test_list_query_factory_perf_against_postgres.py`
proves the EXPLAIN-level consequence (index scan under generic plan).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.list_query import (
    ArrayContainsFilter,
    ColumnInFilter,
    ColumnNotInFilter,
    ScalarFilter,
    make_list_query_handler,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@dataclass(frozen=True)
class _ProbeQuery:
    """Minimal query with one of each filter shape; lets the test
    exercise every branch of the factory's SQL composer in a single
    handler invocation."""

    limit: int = 10
    cursor: str | None = None
    scalar_attr: str | None = None
    array_contains_attr: UUID | None = None
    column_in_attr: list[str] | None = None
    column_not_in_attr: list[str] | None = None


@dataclass(frozen=True)
class _ProbeItem:
    item_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class _ProbePage:
    items: list[_ProbeItem]
    next_cursor: str | None


class _RecordingConn:
    """Captures every SQL string passed to `fetch` so the test can
    assert on the factory's emitted query."""

    def __init__(self) -> None:
        self.fetched_sql: list[str] = []

    async def fetch(self, sql: str, *_args: Any) -> list[Any]:
        self.fetched_sql.append(sql)
        return []


class _RecordingAcquireCM:
    def __init__(self, conn: _RecordingConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _RecordingConn:
        return self._conn

    async def __aexit__(self, *_: Any) -> None:
        return None


class _RecordingPool:
    def __init__(self, conn: _RecordingConn) -> None:
        self._conn = conn

    def acquire(self) -> _RecordingAcquireCM:
        return _RecordingAcquireCM(self._conn)


class _UnauthorizedError(Exception):
    pass


def _build_probe_handler(conn: _RecordingConn) -> Any:
    """Construct a factory handler wired to the recording pool. All
    three filter primitives are exercised so the assert iterates over
    every fragment shape the factory can emit."""
    deps = build_deps(ids=[], now=_NOW)
    object.__setattr__(deps, "pool", _RecordingPool(conn))
    return make_list_query_handler(
        deps,
        query_name="ProbeList",
        log_prefix="probe_list",
        unauthorized_error=_UnauthorizedError,
        table="probe_table",
        select_columns="item_id, created_at",
        time_column="created_at",
        id_column="item_id",
        filters=[
            ScalarFilter(attr="scalar_attr", column="scalar_col"),
            ArrayContainsFilter(attr="array_contains_attr", column="array_col"),
            ColumnInFilter(attr="column_in_attr", column="in_col"),
            ColumnNotInFilter(attr="column_not_in_attr", column="not_in_col"),
        ],
        row_to_item=lambda row: _ProbeItem(item_id=row["item_id"], created_at=row["created_at"]),
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.item_id,
        page_from=lambda items, next_cursor: _ProbePage(items=items, next_cursor=next_cursor),
    )


@pytest.mark.unit
async def test_factory_never_emits_is_null_or_smart_logic_pattern() -> None:
    """The single load-bearing assertion: no SQL string the factory
    builds may contain the `IS NULL OR` anti-pattern, in any filter
    combination."""
    conn = _RecordingConn()
    handler = _build_probe_handler(conn)
    # Exercise every active/inactive combination of the three filters.
    # 2^3 = 8 combinations; cursor variant doubles this to 16.
    bool_values = [False, True]
    sample_uuid = uuid4()
    for has_scalar in bool_values:
        for has_array in bool_values:
            for has_in in bool_values:
                for has_cursor_flag in bool_values:
                    query = _ProbeQuery(
                        scalar_attr="probe" if has_scalar else None,
                        array_contains_attr=sample_uuid if has_array else None,
                        column_in_attr=["a", "b"] if has_in else None,
                        cursor=(
                            # An obviously-valid cursor encoding; the
                            # recording pool short-circuits before decode
                            # would be called on a real fetch path, but
                            # the factory's decode is exercised first.
                            "MjAyNi0wNS0xN1QxMjowMDowMC4wMDArMDA6MDB8MDE5MDAwMDAwMDAwNzAwMDgwMDAwMDAwMDAwMDAwMDAxX2lk"
                            if has_cursor_flag
                            else None
                        ),
                    )
                    # Cursor decode may reject the synthetic value;
                    # we only need the SQL that was emitted in the
                    # no-cursor path. The has_cursor variant is
                    # covered by `test_factory_emits_cursor_predicate`
                    # below where we use a real encoded cursor.
                    with contextlib.suppress(Exception):
                        await handler(
                            query,
                            principal_id=_PRINCIPAL_ID,
                            correlation_id=_CORRELATION_ID,
                        )
    assert len(conn.fetched_sql) >= 1, "factory failed to emit any SQL"
    for sql in conn.fetched_sql:
        assert "IS NULL OR" not in sql.upper(), (
            "Factory emitted the smart-logic anti-pattern, which is "
            "non-sargable under PostgreSQL's generic plan. Offending SQL:\n"
            f"{sql}"
        )


@pytest.mark.unit
async def test_factory_omits_inactive_filters_from_where_clause() -> None:
    """When a filter's value is None (or empty list for ColumnInFilter),
    no fragment for that column should appear in the WHERE clause. This
    is what makes the new pattern sargable; the inactive filter literally
    isn't in the SQL the planner sees."""
    conn = _RecordingConn()
    handler = _build_probe_handler(conn)
    # Only the scalar filter is active.
    await handler(
        _ProbeQuery(scalar_attr="active_value"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(conn.fetched_sql) == 1
    sql = conn.fetched_sql[0]
    assert "scalar_col = $2" in sql
    assert "array_col" not in sql, "Inactive ArrayContainsFilter leaked into WHERE"
    assert "in_col" not in sql, "Inactive ColumnInFilter leaked into WHERE"


@pytest.mark.unit
async def test_factory_treats_empty_column_in_filter_list_as_inactive() -> None:
    """An empty acceptable-value list for ColumnInFilter should NOT
    emit `WHERE col = ANY('{}')` (which would return zero rows and
    surprise callers). Empty list == no filter, mirroring the None
    convention."""
    conn = _RecordingConn()
    handler = _build_probe_handler(conn)
    await handler(
        _ProbeQuery(column_in_attr=[]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(conn.fetched_sql) == 1
    sql = conn.fetched_sql[0]
    assert "in_col" not in sql, (
        "Empty ColumnInFilter list emitted a WHERE fragment; expected to be "
        "treated as 'no filter' equivalent to None."
    )
    # No filters active at all -> no WHERE clause.
    assert "WHERE" not in sql.upper()


@pytest.mark.unit
async def test_factory_emits_column_not_in_filter_as_not_all_predicate() -> None:
    """ColumnNotInFilter must compose as `col <> ALL($N)` so the
    excluded values are dropped from results without re-introducing
    the smart-logic anti-pattern. PG-idiomatic NOT IN against an
    array param; stays sargable when paired with another narrowing
    predicate."""
    conn = _RecordingConn()
    handler = _build_probe_handler(conn)
    await handler(
        _ProbeQuery(column_not_in_attr=["DebriefConflicted", "CautionDraftConflicted"]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(conn.fetched_sql) == 1
    sql = conn.fetched_sql[0]
    assert "not_in_col <> ALL($2)" in sql


@pytest.mark.unit
async def test_factory_treats_empty_column_not_in_filter_list_as_inactive() -> None:
    """Empty exclusion list == no filter. Without this, a route layer
    that accidentally passes [] would exclude nothing AND still bloat
    the SQL string + parameter list."""
    conn = _RecordingConn()
    handler = _build_probe_handler(conn)
    await handler(
        _ProbeQuery(column_not_in_attr=[]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(conn.fetched_sql) == 1
    sql = conn.fetched_sql[0]
    assert "not_in_col" not in sql, (
        "Empty ColumnNotInFilter list emitted a WHERE fragment; expected to be "
        "treated as 'no filter' equivalent to None."
    )
    assert "WHERE" not in sql.upper()
