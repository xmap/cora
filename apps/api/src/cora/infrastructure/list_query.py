"""Cross-BC scaffolding for cursor-paginated list-query handlers.

Mirrors the `update_handler.make_update_handler` precedent (hoisted
at n=3). Every `list_*` query slice runs the same workflow:

  1. Emit `<log_prefix>.start` with the query's headline fields.
  2. Authorize via `deps.authz.authorize(command_name=<query_name>, ...)`;
     raise the BC-local `UnauthorizedError` on `Deny`.
  3. Decode the optional opaque cursor into `(time_at, item_id)`.
  4. If `deps.pool is None` (in-memory test mode), emit
     `<log_prefix>.no_pool` and return an empty page.
  5. Inspect each `FilterSpec`: pull the value from the query via
     `getattr(query, spec.attr)`; if non-None, render the matching
     SQL fragment (`column = $N` for `ScalarFilter`,
     `$N = ANY(column)` for `ArrayContainsFilter`) and append the
     value to the parameter list. NULL values short-circuit the
     filter, no fragment emitted.
  6. Assemble the SQL from `SELECT`, `FROM`, the active filter
     fragments, the optional cursor predicate, the `ORDER BY`, and
     `LIMIT $1`. Each filter combination produces a distinct SQL
     string, so asyncpg's per-connection prepared-statement cache
     keys each combination separately.
  7. Run either the no-cursor or with-cursor SQL with positional
     params: `(limit+1, *filter_values [, cursor_at, cursor_id])`.
  8. Slice the fetched rows to `query.limit`; if a `+1` overflow
     row was returned, encode `next_cursor` from the last kept item.
  9. Emit `<log_prefix>.success` and return the page.

## Why dynamic SQL composition, not `($N IS NULL OR column = $N)`

The "smart logic" pattern ([Markus Winand][1]) builds one SQL
string that handles both "filter present" and "filter omitted"
cases by guarding each filter with `$N IS NULL OR`. Convenient,
and the single-string contract was the obvious first cut. But:

  - Postgres switches a prepared statement to a generic plan after
    five executions (per [PREPARE docs][2]). Under a generic plan
    the planner can't prove the OR's NULL branch unreachable, so
    it falls back to a sequential scan even when the column has a
    perfect index.
  - asyncpg auto-caches prepared statements per connection
    (`statement_cache_size=100` default) and `asyncpg.Pool` reuses
    connections, so the threshold gets crossed in normal
    production traffic.

Composing the SQL per request from only the active filters yields
a tight, sargable WHERE clause that Postgres can plan against
real index statistics every time. Each filter combination becomes
its own prepared-statement cache entry. The set of combinations
is bounded (2^N per list slice, max 8 filters anywhere in the
codebase today, so 256 worst-case for `list_clearances`).

The shape matches [SQLAlchemy Core's idiomatic optional-filter
pattern][3] (chained `.where()` calls guarded by `if value is not
None`) and the composition primitive in [psycopg3's `sql`
module][4]; we hand-roll it here because asyncpg has no built-in
equivalent. See [[project_deferred]] for the deferred psycopg3
migration evaluation that would let us drop the hand-rolled
composer in favor of `sql.Composed`.

[1]: https://use-the-index-luke.com/sql/where-clause/obfuscation/smart-logic
[2]: https://www.postgresql.org/docs/current/sql-prepare.html
[3]: https://docs.sqlalchemy.org/en/20/tutorial/data_select.html
[4]: https://www.psycopg.org/psycopg3/docs/api/sql.html

## What the slice owns vs. what the factory owns

  - **Slice owns** the projection table name, the SELECT column
    list, the `Item` / `Page` dataclasses, the `FilterSpec` list,
    the time-column / id-column names for ordering and cursor
    keys, the query/row/cursor mapping functions, and the
    `UnauthorizedError` class. All of these are domain choices.
  - **Factory owns** the workflow boilerplate (authorize / cursor
    decode / pool short-circuit / fetch / slice / next-cursor /
    log triplet) plus the SQL composer, so the structured-log
    field order and the SQL shape stay byte-stable across BCs.

## Per-slice inputs

  - `query_name: str` — canonical PascalCase query name
    (for example `"ListRuns"`). Used in `authorize` and log lines.
  - `log_prefix: str` — slice name used for log-line prefixes
    (for example `"list_runs"` -> `list_runs.start` / `.denied` /
    `.no_pool` / `.success`).
  - `unauthorized_error: type[Exception]` — BC-local
    `UnauthorizedError` raised on `Deny`. Per-BC (not hoisted) per
    [[project_genesis_error_classes]] so log search distinguishes
    which BC denied a query.
  - `table: str` — projection table name (`"proj_run_summary"`).
  - `select_columns: str` — comma-separated SELECT column list,
    no leading SELECT keyword. The slice writes this so domain
    reviewers can read it inline next to the slice rather than
    inferring it from the factory's column-name handling.
  - `time_column: str` — timestamp column used in both `ORDER BY`
    and the cursor predicate (`(time_col, id_col) > ($N, $M)`).
    Typically `"created_at"`; supplies / procedures / clearances
    use `"registered_at"` per their domain naming.
  - `id_column: str` — the projection's primary-key column used
    in `ORDER BY` and the cursor predicate (for example `"run_id"`).
  - `filters: Sequence[FilterSpec]` — declarative filter list,
    one `ScalarFilter` or `ArrayContainsFilter` per filter the
    query exposes. Order matters: it defines the asyncpg
    parameter order ($2 .. $N) and the log-field order. Empty
    sequence is fine (for example `list_zones`).
  - `row_to_item: Callable[[Any], Item]` — maps an asyncpg
    `Record` to the slice's `Item` dataclass.
  - `item_cursor_at: Callable[[Item], datetime]` /
    `item_cursor_id: Callable[[Item], UUID]` — extract the cursor
    key fields from a page item.
  - `page_from: Callable[[list[Item], str | None], Page]` —
    constructs the slice's `Page` dataclass from the kept items
    and the optional `next_cursor`.
  - `extract_log_fields: Callable[[Q], dict[str, Any]] | None` —
    OPTIONAL extractor for per-slice fields on the `.start` line
    (for example `status`, `plan_id` for `list_runs`). The returned dict
    is merged between `limit` and `has_cursor` so existing log
    consumers see the same field order. Default `None` means no
    extras (matches slices with only `limit + cursor`).

## Safety: identifier interpolation

`table`, `select_columns`, `time_column`, `id_column`, and the
`column` strings on each `FilterSpec` are interpolated into the
SQL string with f-strings. They are NOT user input: every
production call site passes module-level string literals from a
slice's `handler.py`. The contract is "caller owns identifier
trust"; we do not validate or quote identifiers in the composer.
Values are always parameterized (`$N`), never interpolated.

## Why a free function (not a base class)

Same rationale as `cora.infrastructure.update_handler`: a free
function lets each slice bind its own narrow `Handler` Protocol
around the shared body without dragging the cross-BC abstraction
into the type lattice.

## Growth rule (READ BEFORE ADDING A NEW PRIMITIVE)

The factory exposes a closed, declarative set of filter
primitives. No escape hatch. New primitives ship only when the
shape they express is **broadly useful** across the codebase, not
to accommodate one slice's idiosyncrasy.

When a slice doesn't fit, the default action is **force
conformance**: examine whether the slice is expressing a real
shape the factory should cover or a slice-level smell. The
historical 16/17 fit ratio is evidence that the existing
primitives match the domain; if conformance ever drops below
~13/17 it's the factory that's over-fitted, not the slices.

Examples of the rule in action:

  - `ColumnInFilter` shipped because `column = ANY($N::TYPE[])`
    is the shape any "list X where status in [A, B]" query wants,
    used today by `list_cautions` for both `statuses` and
    `severities` and reusable across the codebase for any closed-
    enum filter.
  - `list_cautions`'s pre-refactor `(CASE severity WHEN ... END)
    >= $N` and `status` sentinel-with-default-and-'all' were NOT
    accommodated; they were domain-modeling smells (workarounds
    for a stored text column treated as ordered; conflation of
    "filter control" with "filter value"). Fixed by route-layer
    translation, not factory growth.

When in doubt: would a fresh greenfield slice plausibly want this
primitive? If yes, add it. If no, push back on the slice.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class ScalarFilter:
    """Equality filter: emits `WHERE <column> = $N` when the query
    attribute is non-None; emits nothing when None.

    `column` defaults to `attr` when omitted (the common case where
    the query field name and the projection column name match).
    """

    attr: str
    column: str | None = None


@dataclass(frozen=True)
class ArrayContainsFilter:
    """Array-membership filter: emits `WHERE $N = ANY(<column>)`
    when the query attribute is non-None; emits nothing when None.

    Used for projection columns that are arrays (for example,
    `target_asset_ids` on Procedure, the four `*_binding_ids` on
    Clearance). The query field is typically singular (the value
    to search for); the column is plural (the array to search in).
    `column` is required, no default.
    """

    attr: str
    column: str


@dataclass(frozen=True)
class ColumnInFilter:
    """Set-membership filter: emits `WHERE <column> = ANY($N)` when
    the query attribute is a non-empty list; emits nothing when
    None or empty.

    Used for "filter by one-of these acceptable values" patterns
    against scalar columns. Inverse direction of `ArrayContainsFilter`:
    here the column is scalar and the parameter is the list of
    candidates. The route layer translates user-facing UX (for example a
    min_severity ladder, a multi-select status filter) into the
    canonical list before constructing the query dataclass.

    `column` defaults to `attr` when omitted. Empty list is treated
    as "no filter" to match the None semantics: an empty acceptable-
    value set would otherwise return zero rows, which is rarely
    what the caller meant.
    """

    attr: str
    column: str | None = None


@dataclass(frozen=True)
class ColumnNotInFilter:
    """Set-exclusion filter: emits `WHERE <column> <> ALL($N)` when the
    query attribute is a non-empty sequence; emits nothing when None
    or empty.

    The negative-list counterpart to `ColumnInFilter`. Used for
    "filter out one-or-more values" patterns -- e.g., excluding
    audit-only DecisionChoice values from analytic queries that
    compute outcome rates. `<> ALL($1)` is the PG-idiomatic NOT-IN
    against an array parameter and stays sargable on the scalar
    column's index when other predicates narrow the row set first.

    `column` defaults to `attr` when omitted. Empty list is treated
    as "no filter" to match the `ColumnInFilter` symmetry and avoid
    the route layer accidentally turning "user passed nothing" into
    "WHERE FALSE".
    """

    attr: str
    column: str | None = None


FilterSpec = ScalarFilter | ArrayContainsFilter | ColumnInFilter | ColumnNotInFilter


class _Query(Protocol):
    """Structural contract every `list_*` query dataclass satisfies."""

    @property
    def limit(self) -> int: ...

    @property
    def cursor(self) -> str | None: ...


class _ListQueryHandler[Q: _Query, Page](Protocol):
    """The factory's return shape.

    Each slice's locally-declared `Handler` Protocol is identical
    in shape (Q is invariant on the call side because slices
    parameterize the factory with their concrete query type), so
    the returned callable assigns to it without an explicit cast.
    """

    async def __call__(
        self,
        query: Q,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Page: ...


def _filter_column(spec: FilterSpec) -> str:
    """Resolve the SQL column name for a filter spec.

    `ArrayContainsFilter.column` is required (no default); the
    other two specs default `column` to `attr` when omitted.
    """
    if isinstance(spec, ArrayContainsFilter):
        return spec.column
    return spec.column if spec.column is not None else spec.attr


def _render_filter_fragment(spec: FilterSpec, param_number: int) -> str:
    column = _filter_column(spec)
    if isinstance(spec, ScalarFilter):
        return f"{column} = ${param_number}"
    if isinstance(spec, ArrayContainsFilter):
        return f"${param_number} = ANY({column})"
    if isinstance(spec, ColumnNotInFilter):
        return f"{column} <> ALL(${param_number})"
    # ColumnInFilter: column scalar, parameter is the candidate list.
    return f"{column} = ANY(${param_number})"


def _active_filter_value(spec: FilterSpec, value: Any) -> bool:
    """A filter is active iff the slice would emit a WHERE fragment.

    None is always inactive (matches the `getattr` default). For
    `ColumnInFilter` / `ColumnNotInFilter`, an empty list is also
    inactive: an empty IN would return zero rows + an empty NOT IN
    would exclude nothing, neither of which the caller likely meant.
    The route layer omits the filter instead of passing [].
    """
    if value is None:
        return False
    if isinstance(spec, ColumnInFilter | ColumnNotInFilter):
        return len(value) > 0
    return True


def _build_sql(
    *,
    select_columns: str,
    table: str,
    active_filter_fragments: list[str],
    time_column: str,
    id_column: str,
    cursor_param_start: int | None,
) -> str:
    """Assemble the SELECT from its composable parts.

    `cursor_param_start` is the param number for `cursor_at`
    (`cursor_id` is the next one) when the cursor predicate should
    be appended; None when the call has no cursor.
    """
    where_parts = list(active_filter_fragments)
    if cursor_param_start is not None:
        where_parts.append(
            f"({time_column}, {id_column}) > (${cursor_param_start}, ${cursor_param_start + 1})"
        )
    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + "\n  AND ".join(where_parts) + "\n"
    return (
        f"SELECT {select_columns}\n"
        f"FROM {table}\n"
        f"{where_clause}"
        f"ORDER BY {time_column} ASC, {id_column} ASC\n"
        f"LIMIT $1"
    )


def make_list_query_handler[Q: _Query, Item, Page](
    deps: Kernel,
    *,
    query_name: str,
    log_prefix: str,
    unauthorized_error: type[Exception],
    table: str,
    select_columns: str,
    time_column: str,
    id_column: str,
    filters: Sequence[FilterSpec],
    row_to_item: Callable[[Any], Item],
    item_cursor_at: Callable[[Item], datetime],
    item_cursor_id: Callable[[Item], UUID],
    page_from: Callable[[list[Item], str | None], Page],
    extract_log_fields: Callable[[Q], dict[str, Any]] | None = None,
) -> _ListQueryHandler[Q, Page]:
    """Build a cursor-paginated list-query handler for one slice.

    See module docstring for the slice/factory split, the
    per-slice inputs, and the rationale for dynamic SQL
    composition over the `($N IS NULL OR column = $N)` pattern.
    """
    log = get_logger(log_prefix)

    async def handler(
        query: Q,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Page:
        extras: dict[str, Any] = extract_log_fields(query) if extract_log_fields is not None else {}

        log.info(
            f"{log_prefix}.start",
            query_name=query_name,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            **extras,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=query_name,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            log.info(
                f"{log_prefix}.denied",
                query_name=query_name,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise unauthorized_error(decision.reason)

        cursor_at: datetime | None = None
        cursor_id: UUID | None = None
        if query.cursor is not None:
            cursor_at, cursor_id = decode_cursor(query.cursor)

        if deps.pool is None:
            log.info(
                f"{log_prefix}.no_pool",
                query_name=query_name,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return page_from([], None)

        # Compose only the WHERE fragments for filters with active
        # values (non-None scalars, non-empty lists for ColumnInFilter).
        # $1 is reserved for `limit + 1`, so filter params start at $2.
        active_fragments: list[str] = []
        filter_values: list[Any] = []
        next_param = 2
        for spec in filters:
            value = getattr(query, spec.attr)
            if not _active_filter_value(spec, value):
                continue
            active_fragments.append(_render_filter_fragment(spec, next_param))
            filter_values.append(value)
            next_param += 1

        cursor_param_start = next_param if cursor_at is not None else None
        sql = _build_sql(
            select_columns=select_columns,
            table=table,
            active_filter_fragments=active_fragments,
            time_column=time_column,
            id_column=id_column,
            cursor_param_start=cursor_param_start,
        )

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(sql, query.limit + 1, *filter_values)
            else:
                rows = await conn.fetch(
                    sql,
                    query.limit + 1,
                    *filter_values,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items: list[Item] = [row_to_item(row) for row in kept]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=item_cursor_at(last),
                item_id=item_cursor_id(last),
            )

        log.info(
            f"{log_prefix}.success",
            query_name=query_name,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return page_from(items, next_cursor)

    return handler


__all__ = [
    "ArrayContainsFilter",
    "ColumnInFilter",
    "ColumnNotInFilter",
    "FilterSpec",
    "ScalarFilter",
    "make_list_query_handler",
]
