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
"declare or exclude, in writing" finding. Whether the exporter actually
pulls their rows into a published bundle, or excludes them as
operational telemetry, is a separate, still-open call for the exporter
step; this registry only has to make every table reachable and refuse
to silently drop any of them.

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
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import asyncpg

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level, matching the other
# entries-table readers (e.g. postgres_procedure_activity_lookup.py).

EntriesReader = Callable[[asyncpg.Connection, UUID | str], Awaitable[list[asyncpg.Record]]]


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


def _spec(
    *,
    kind: str,
    table: str,
    envelope_class: str | None,
    scope_column: str,
    order_by: tuple[str, ...],
    scope_type: type[UUID] | type[str] = UUID,
) -> EntriesTableSpec:
    return EntriesTableSpec(
        kind=kind,
        table=table,
        envelope_class=envelope_class,
        scope_column=scope_column,
        scope_type=scope_type,
        order_by=order_by,
        reader=_make_reader(table, scope_column, order_by),
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
    ),
    _spec(
        kind="capture_probe",
        table="entries_run_capture_probes",
        envelope_class=None,
        scope_column="capture_code",
        order_by=("event_id",),
        scope_type=str,
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
