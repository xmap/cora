"""EnclosureSummaryProjection: folds the Enclosure aggregate's events
into the `proj_enclosure_summary` read model that backs future
`GET /enclosures` slices.

Subscribed events:
  - EnclosureRegistered     -> INSERT (lifecycle='Active',
                                       permit_status='Unknown',
                                       last_*=NULL,
                                       registered_at=occurred_at)
  - EnclosurePermitObserved -> UPDATE permit_status=to_status,
                                      last_permit_status_changed_at=occurred_at,
                                      last_permit_status_reason=reason,
                                      last_trigger=trigger,
                                      last_source_kind, last_source_id
                                      (split from monitor_ref),
                                      last_source_observed_at=observed_at

Two clocks, two columns, and the distinction is the point.
`last_permit_status_changed_at` is CORA's: the event's `occurred_at`,
stamped by the Clock port when the handler appended. It says when CORA
recorded a transition. `last_source_observed_at` is the substrate's own
time for the reading behind that transition, and is NULL whenever the
substrate reported none, which at APS 2-BM is every reading. Neither
substitutes for the other, and nothing in this projection may fill one
from the other.

Both advance only on a CHANGE, because the decider emits no event for
an identical-status observation. A stale value means "no transition
since", never "not observed since"; distinguishing those is the job of
monitoring-coverage recording, not of this table.
  - EnclosureDecommissioned -> UPDATE lifecycle='Decommissioned',
                                      decommissioned_at=occurred_at,
                                      decommissioned_by=decommissioned_by
                                      (permit_status preserved untouched
                                       as audit trail per the two-axis
                                       orthogonality lock)

Permit-status and lifecycle are orthogonal axes per
[[project_enclosure_stage1_design]] (D6.L2 observation-axis-only,
D10-L1 no Bypassed state). `EnclosureDecommissioned` does NOT clear
permit_status: the last-known observation stays on the row as audit
for post-mortem review.

## Address-tuple uniqueness on (facility_code, name)

The migration's `proj_enclosure_summary_address_uq` UNIQUE INDEX on
`(facility_code, name)` is PARTIAL on `WHERE lifecycle =
'Active'`: Decommissioned rows do not count toward uniqueness, so an
operator who decommissions a mistaken Enclosure can re-register at
the same address with a fresh enclosure_id. Mirrors the Supply
partial-UNIQUE address pattern per [[project_supply_sector_disposition]].

The live-path uniqueness check is upstream in the register_enclosure
handler (concurrency loses cleanly on the second writer per
`append(expected_version=0)`); this projection UNIQUE INDEX is
defense-in-depth against projection-rebuild drift, out-of-band SQL,
and concurrent active registrations at the same address. The genesis
INSERT is SAVEPOINT-wrapped so a UniqueViolation rolls back ONLY the
inner write; the worker's outer batch transaction stays clean and the
bookmark advances. Without the SAVEPOINT, asyncpg raises
InFailedSQLTransactionError on the next SQL.

When two operators concurrently register enclosures at the same
(facility_code, name) address, the second `EnclosureRegistered`
event may land in the event store (no decider gate beyond per-stream
optimistic concurrency) but its projection INSERT raises
`asyncpg.UniqueViolationError`. Day-one operational handling: catch
the unique-violation, log a structured WARN, and return successfully
so the projection bookmark advances and the worker keeps running.
The duplicate Enclosure event sits in the event log as a permanent
audit-record of the operator mistake; the projection has only the
first row.

## monitor_ref splitting

`EnclosurePermitObserved.monitor_ref` carries substream attribution
as the string '{source_kind}:{source_id}'. The projection splits on
the first ':' at write time so consumers query
`WHERE last_source_kind = 'EpicsPv'` without LIKE-substring
fragility. Both columns are nullable and stay NULL when the event's
monitor_ref is absent (Operator-triggered observations land with
monitor_ref omitted; the split behaviour gracefully degrades).

## last_observed_* columns are projection-only

`last_observed_at` / `last_observed_reason` / `last_trigger` /
`last_source_kind` / `last_source_id` are denormalized read-side
audit fields per the L-proj-2 lock; they are NOT carried on the
aggregate state (Slim Aggregate per L-state-1). Consumers asking
"when was this last observed and by what?" hit the projection row
without folding the event stream.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_log = get_logger(__name__)

_INSERT_ENCLOSURE_SQL = """
INSERT INTO proj_enclosure_summary
    (enclosure_id, name, facility_code,
     lifecycle, permit_status,
     registered_at, registered_by,
     last_permit_status_changed_at, last_permit_status_reason, last_trigger,
     last_source_kind, last_source_id, last_source_observed_at,
     decommissioned_at, decommissioned_by)
VALUES ($1, $2, $3,
        'Active', 'Unknown',
        $4, $5,
        NULL, NULL, NULL,
        NULL, NULL, NULL,
        NULL, NULL)
ON CONFLICT (enclosure_id) DO NOTHING
"""

_UPDATE_PERMIT_OBSERVED_SQL = """
UPDATE proj_enclosure_summary
SET permit_status = $2,
    last_permit_status_changed_at = $3,
    last_permit_status_reason = $4,
    last_trigger = $5,
    last_source_kind = $6,
    last_source_id = $7,
    last_source_observed_at = $8,
    updated_at = now()
WHERE enclosure_id = $1
"""

_UPDATE_DECOMMISSIONED_SQL = """
UPDATE proj_enclosure_summary
SET lifecycle = 'Decommissioned',
    decommissioned_at = $2,
    decommissioned_by = $3,
    updated_at = now()
WHERE enclosure_id = $1
"""


def _optional_timestamp(raw: object) -> datetime | None:
    """Parse an optional ISO-8601 payload time, tolerating its absence.

    Two different absences arrive here and both answer None. A payload
    written before `observed_at` existed has no key at all, and the
    2-BM store holds such events today; the projection re-reads them on
    every rebuild and the monitor re-folds them on every decision, so an
    unguarded `payload["observed_at"]` would break the live permit
    monitor immediately rather than at some later restore. A payload
    written after it exists carries an explicit null whenever the
    substrate reported no time, which at 2-BM is every reading.

    Follows the `monitor_ref` precedent one field over, which uses the
    same defensive `.get()` for the same reason.
    """
    return datetime.fromisoformat(raw) if isinstance(raw, str) else None


def _split_monitor_ref(monitor_ref: str | None) -> tuple[str | None, str | None]:
    """Split '{source_kind}:{source_id}' into the two projection columns.

    Returns `(None, None)` when monitor_ref is absent so consumers can
    use the equality predicate without coalescing. A monitor_ref with
    no ':' separator (defensive: today's decider rejects this, but the
    projection stays robust against historical or hand-crafted events)
    routes the full string to `last_source_kind` with `last_source_id`
    left NULL.
    """
    if monitor_ref is None:
        return (None, None)
    head, sep, tail = monitor_ref.partition(":")
    if not sep:
        return (head, None)
    return (head, tail)


class EnclosureSummaryProjection:
    """Maintains the `proj_enclosure_summary` read model."""

    name = "proj_enclosure_summary"
    subscribed_event_types = frozenset(
        {
            "EnclosureRegistered",
            "EnclosurePermitObserved",
            "EnclosureDecommissioned",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "EnclosureRegistered":
            payload = event.payload
            try:
                async with conn.transaction():
                    await conn.execute(
                        _INSERT_ENCLOSURE_SQL,
                        UUID(payload["enclosure_id"]),
                        payload["name"],
                        payload["facility_code"],
                        datetime.fromisoformat(payload["occurred_at"]),
                        UUID(payload["registered_by"]),
                    )
            except asyncpg.UniqueViolationError:
                _log.warning(
                    "enclosure_summary_projection.duplicate_address_skipped",
                    enclosure_id=payload["enclosure_id"],
                    facility_code=payload["facility_code"],
                    name=payload["name"],
                    event_id=str(event.event_id),
                )
            return

        if event.event_type == "EnclosurePermitObserved":
            payload = event.payload
            source_kind, source_id = _split_monitor_ref(payload.get("monitor_ref"))
            await conn.execute(
                _UPDATE_PERMIT_OBSERVED_SQL,
                UUID(payload["enclosure_id"]),
                payload["to_status"],
                datetime.fromisoformat(payload["occurred_at"]),
                payload["reason"],
                payload["trigger"],
                source_kind,
                source_id,
                _optional_timestamp(payload.get("observed_at")),
            )
            return

        if event.event_type == "EnclosureDecommissioned":
            payload = event.payload
            await conn.execute(
                _UPDATE_DECOMMISSIONED_SQL,
                UUID(payload["enclosure_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
                UUID(payload["triggered_by"]),
            )
            return

        return


__all__ = ["EnclosureSummaryProjection"]
