"""Registry: logbook ``kind`` -> (table, order key, reader).

Per `project_record_export_v3.md` F0/F2 and
`project_record_is_two_tier.md`. The exporter walks the event stream and,
on each ``<X>LogbookOpened`` envelope, reads the envelope's ``kind`` (a
bare ``str``, not a closed enum) and resolves it through this ONE
registry to the entries table that holds the fine-grained doing. An
unknown ``kind`` refuses loudly rather than being skipped.

Nine entries, not six. Six kinds come from an envelope event on the
main stream; three tables, `entries_run_feed_heartbeats`,
`entries_enclosure_permit_probes`, and `entries_run_capture_probes`,
have no envelope at all and are declared here explicitly, with
`envelope_class` set to `None`, per `project_record_is_two_tier.md`'s
"declare or exclude, in writing" finding. The operator decided at S4
(`project_record_completeness_design.md`) that all three are pulled
into the published bundle rather than excluded as operational
telemetry; `unscoped_reader` below is how S5a/S5b/S5c carried that
decision into code. This registry's own job stays the same regardless:
make every table reachable and refuse to silently drop any of them.

The order key lives per kind because `sampled_at` exists on only four of
the nine tables (activity, diagnostic, outcome, observation). The other
five order by `event_id` alone: CORA mints it with `UUIDv7Generator`, so
it is total and insertion-ordered without a separate timestamp column,
and `occurred_at` is never the tiebreak because it ties across a whole
append batch (one Clock read per handler call).

The six envelope-driven tables are scoped by `logbook_id`, the join
column the envelope carries. Heartbeats and probes are not
Logbook-and-Entry instances (no `logbook_id` column at all) and are
scoped by their owning aggregate's id instead: `run_id` for heartbeats,
`enclosure_id` for permit probes. `entries_run_capture_probes` differs
from BOTH: a capture code has no backing aggregate at all (see that
table's migration header and `run.aggregates.run.capture_probes`'s
module docstring), so it scopes on `capture_code`, a deployment-declared
string, not a UUID. `EntriesReader`'s scope-id type is widened
(`UUID | str`) for exactly this one case; every other spec still passes
a `UUID` at runtime, unaffected.

`unscoped_reader` (S5,
`project_record_completeness_design.md`) is a SEPARATE, optional field
rather than a nullable scope argument on `reader`: an unscoped read
(`SELECT * FROM <table> ORDER BY ...`, no `WHERE`) is a different
operation from a scoped one, and letting a caller pass `None` as a
scope id against one of the six envelope specs would silently read the
whole table where the exporter meant to read one logbook's slice.
`heartbeat` (S5a), `capture_probe` (S5b) and `permit_probe` (S5c) all
set it now; every other spec's `reader` and its own call sites are
unchanged. Every kind owed its own disclosure review before a bundle
could carry it; see each kind's disposition entries in
`_redact_tier2.py` and its own slice's commit message for the
reasoning, including `permit_probe.status_claimed`'s verdict (S5c).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import asyncpg

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level, matching the other
# entries-table readers (e.g. postgres_procedure_activity_lookup.py).

EntriesReader = Callable[[asyncpg.Connection, UUID | str], Awaitable[list[asyncpg.Record]]]
UnscopedEntriesReader = Callable[[asyncpg.Connection], Awaitable[list[asyncpg.Record]]]


@dataclass(frozen=True, slots=True)
class EntriesTableSpec:
    """One registry row: how to read one kind's entries-tier rows.

    `envelope_class` names the `*LogbookOpened` class that carries this
    kind on the main stream, or `None` for the three tables with no
    envelope. `scope_column` is the column `reader` filters on: the
    envelope's `logbook_id` for the six logbook-backed kinds, the owning
    aggregate's id for `heartbeat`/`permit_probe`, and `capture_code` (a
    deployment-declared string, no backing aggregate) for
    `capture_probe`. `scope_type` names which of those `reader` expects
    (`UUID` for every spec but `capture_probe`, which is `str`) so a
    generic caller can self-classify a spec rather than hardcoding an
    exclusion list keyed on `kind` (see
    `tests/integration/test_record_export_registry_postgres.py`, which
    derives its UUID-scoped parametrization from this field).
    """

    kind: str
    table: str
    envelope_class: str | None
    scope_column: str
    scope_type: type[UUID] | type[str]
    order_by: tuple[str, ...]
    reader: EntriesReader
    unscoped_reader: UnscopedEntriesReader | None = None
    """Reads every row of `table`, unscoped, when set. `heartbeat` (S5a),
    `capture_probe` (S5b) and `permit_probe` (S5c) all set it today;
    every six-envelope spec leaves it `None`. See the module docstring."""


class UnknownLogbookKindError(LookupError):
    """A `kind` with no registry entry. Refuses loudly rather than skipping."""

    def __init__(self, kind: str) -> None:
        super().__init__(
            f"no entries-table registry entry for logbook kind {kind!r}; "
            "an unknown kind must not be skipped"
        )
        self.kind = kind


def _make_reader(table: str, scope_column: str, order_by: tuple[str, ...]) -> EntriesReader:
    # table, scope_column and order_by are all registry-declared constants
    # below, never caller input, so the interpolation cannot carry
    # attacker-controlled SQL.
    sql = f"SELECT * FROM {table} WHERE {scope_column} = $1 ORDER BY {', '.join(order_by)}"

    async def read(conn: asyncpg.Connection, scope_id: UUID | str) -> list[asyncpg.Record]:
        return await conn.fetch(sql, scope_id)

    return read


def _make_unscoped_reader(table: str, order_by: tuple[str, ...]) -> UnscopedEntriesReader:
    """`SELECT * FROM <table> ORDER BY <order_by>`, no `WHERE`.

    `table` and `order_by` are registry-declared constants below, never
    caller input, so the interpolation cannot carry attacker-controlled
    SQL, matching `_make_reader`'s reasoning.

    Unbounded: fetches the whole table in one round trip. DECIDED at S5b
    (`capture_probe`, `project_record_completeness_design.md`): one fetch
    stays acceptable for now, not because the row count is small (it is
    not, and it does not stabilize -- `run.aggregates.run.capture_probes`'s
    own docstring documents a per-(capture_code, PV) rate from zero, while
    the substrate is reachable and `capture_watch_probe_tick_seconds` is
    left at its push-only default, up to roughly 8,640 rows/day/PV while a
    code's substrate is fully unreachable, and this repo has no retention
    policy on this table at any rate), but because a streaming cursor HERE
    alone would not lower the export's peak memory: `export_record`
    already holds every row of every kind it reads in one place at once
    (`ExportedRecord.logbooks`, a `dict` of tuples), so the rows would
    still all end up materialized before a single bundle file is written.
    Swapping this call for an `asyncpg` server-side cursor without also
    changing how `ExportedRecord` and `_bundle.write_bundle` consume a
    kind's rows would move the buffering point, not remove it, and would
    claim a memory fix it did not deliver. Trigger for revisiting, per
    this design's own already-locked phrasing for the identical risk on
    this same table (see the design memo's Watch items): the first export
    measured in minutes. The fix at that point is coordinated across this
    reader, `ExportedRecord`'s shape, and the bundle writer, not a cursor
    swapped in here alone.

    RE-EXAMINED at S5c (`permit_probe`, now wired the same way): this is
    the largest unscoped table in the tier, `count(*)` reported at
    50,085 rows across two enclosures at 21:00 CDT 2026-08-17, growing
    on a 60-second probe tick per enclosure -- roughly five times the
    9,554 `capture_probe` figure S5a recorded (cbab110f1c) as a
    forward-looking note about that table's own eventual disposition;
    S5b's own commit (937abe4707) explicitly could NOT re-measure that
    figure from its session, so this comparison is against the last
    recorded number for that table, not a number S5b itself confirmed.
    Still growing without a retention policy. The argument above is
    about WHERE the buffering happens, not how many rows fit in it, and
    that argument is row-count-independent: it still holds at this
    size, because `ExportedRecord` still materializes every kind's rows
    in one dict regardless of which kind is largest, so a cursor
    swapped in here alone would still just move the same rows to a
    different Python object. What DOES scale with row count is
    wall-clock and network transfer, neither measured directly this
    session (arcturus, the pilot database, was not reachable from this
    environment; the count above is the figure this slice was given,
    not one this session queried itself). Fifty thousand rows of seven
    narrow columns each is not yet the "export measured in minutes"
    trigger this design already named as the point to revisit; it is
    the closest any unscoped table has come to it so far, which is
    worth carrying forward rather than re-deciding silently next time a
    table in this tier grows past it.
    """
    sql = f"SELECT * FROM {table} ORDER BY {', '.join(order_by)}"

    async def read(conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return await conn.fetch(sql)

    return read


def _spec(
    *,
    kind: str,
    table: str,
    envelope_class: str | None,
    scope_column: str,
    order_by: tuple[str, ...],
    scope_type: type[UUID] | type[str] = UUID,
    unscoped: bool = False,
) -> EntriesTableSpec:
    return EntriesTableSpec(
        kind=kind,
        table=table,
        envelope_class=envelope_class,
        scope_column=scope_column,
        scope_type=scope_type,
        order_by=order_by,
        reader=_make_reader(table, scope_column, order_by),
        unscoped_reader=_make_unscoped_reader(table, order_by) if unscoped else None,
    )


_ENTRIES: tuple[EntriesTableSpec, ...] = (
    _spec(
        kind="verdict",
        table="entries_conduit_verdicts",
        envelope_class="ConduitLogbookOpened",
        scope_column="logbook_id",
        order_by=("event_id",),
    ),
    _spec(
        kind="inference",
        table="entries_decision_inferences",
        envelope_class="DecisionLogbookOpened",
        scope_column="logbook_id",
        order_by=("event_id",),
    ),
    _spec(
        kind="activity",
        table="entries_operation_procedure_activities",
        envelope_class="ProcedureActivitiesLogbookOpened",
        scope_column="logbook_id",
        order_by=("sampled_at", "event_id"),
    ),
    _spec(
        kind="diagnostic",
        table="entries_operation_procedure_diagnostics",
        envelope_class="ProcedureDiagnosticLogbookOpened",
        scope_column="logbook_id",
        order_by=("sampled_at", "event_id"),
    ),
    _spec(
        kind="outcome",
        table="entries_operation_procedure_outcomes",
        envelope_class="ProcedureOutcomeLogbookOpened",
        scope_column="logbook_id",
        order_by=("sampled_at", "event_id"),
    ),
    _spec(
        kind="observation",
        table="entries_run_observations",
        envelope_class="RunObservationLogbookOpened",
        scope_column="logbook_id",
        order_by=("sampled_at", "event_id"),
    ),
    _spec(
        kind="heartbeat",
        table="entries_run_feed_heartbeats",
        envelope_class=None,
        scope_column="run_id",
        order_by=("event_id",),
        unscoped=True,
    ),
    _spec(
        # Renamed from the bare "probe" (slice 16): a second, unrelated
        # probe kind (`capture_probe`, below) now exists, and the bare
        # name would silently read as either. No data migration needed:
        # `envelope_class=None` means this literal never lands in an
        # event payload, only in this registry, `_redact_tier2.py`, and
        # their own tests.
        kind="permit_probe",
        table="entries_enclosure_permit_probes",
        envelope_class=None,
        scope_column="enclosure_id",
        order_by=("event_id",),
        unscoped=True,
    ),
    _spec(
        kind="capture_probe",
        table="entries_run_capture_probes",
        envelope_class=None,
        scope_column="capture_code",
        order_by=("event_id",),
        scope_type=str,
        unscoped=True,
    ),
)

_REGISTRY: dict[str, EntriesTableSpec] = {spec.kind: spec for spec in _ENTRIES}


def resolve(kind: str) -> EntriesTableSpec:
    """Look up `kind`'s table spec.

    Raises `UnknownLogbookKindError` rather than returning `None`: an
    envelope carrying a kind this registry has never heard of must stop
    the export, not be skipped.
    """
    try:
        return _REGISTRY[kind]
    except KeyError:
        raise UnknownLogbookKindError(kind) from None


def all_specs() -> tuple[EntriesTableSpec, ...]:
    """Every registered spec, in declaration order."""
    return _ENTRIES


def registered_envelope_classes() -> frozenset[str]:
    """Every `*LogbookOpened` class name named by a registry entry."""
    return frozenset(spec.envelope_class for spec in _ENTRIES if spec.envelope_class is not None)
