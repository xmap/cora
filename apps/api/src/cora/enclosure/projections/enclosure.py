"""EnclosureSummaryProjection: folds the Enclosure aggregate's events
into the `proj_enclosure_summary` read model that backs future
`GET /enclosures` slices.

Subscribed events:
  - EnclosureRegistered     -> INSERT (lifecycle='Active',
                                       permit_status='Unknown',
                                       last_observed_*=NULL,
                                       registered_at=occurred_at)
  - EnclosurePermitObserved -> UPDATE permit_status=to_status,
                                      last_observed_at=occurred_at,
                                      last_observed_reason=reason,
                                      last_trigger=trigger,
                                      last_source_kind, last_source_id
                                      (split from monitor_ref)
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

## Address-tuple uniqueness on (containing_asset_id, name)

The migration's `proj_enclosure_summary_address_uq` UNIQUE INDEX on
`(containing_asset_id, name)` is PARTIAL on `WHERE lifecycle =
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
(containing_asset_id, name) address, the second `EnclosureRegistered`
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
    (enclosure_id, name, containing_asset_id,
     lifecycle, permit_status,
     registered_at, registered_by,
     last_observed_at, last_observed_reason, last_trigger,
     last_source_kind, last_source_id,
     decommissioned_at, decommissioned_by)
VALUES ($1, $2, $3,
        'Active', 'Unknown',
        $4, $5,
        NULL, NULL, NULL,
        NULL, NULL,
        NULL, NULL)
ON CONFLICT (enclosure_id) DO NOTHING
"""

_UPDATE_PERMIT_OBSERVED_SQL = """
UPDATE proj_enclosure_summary
SET permit_status = $2,
    last_observed_at = $3,
    last_observed_reason = $4,
    last_trigger = $5,
    last_source_kind = $6,
    last_source_id = $7,
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
                        UUID(payload["containing_asset_id"]),
                        datetime.fromisoformat(payload["occurred_at"]),
                        UUID(payload["registered_by"]),
                    )
            except asyncpg.UniqueViolationError:
                _log.warning(
                    "enclosure_summary_projection.duplicate_address_skipped",
                    enclosure_id=payload["enclosure_id"],
                    containing_asset_id=payload["containing_asset_id"],
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
