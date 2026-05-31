"""EventStore port: append + load events with optimistic concurrency.

The Postgres adapter implements this against a single `events` table
with `UNIQUE(stream_type, stream_id, version)` for optimistic concurrency. The
load path returns raw stored events; callers fold them with their own evolver
function.

When snapshots are added later, `load` will internally read the latest snapshot
and replay only the events after it; the contract returned to callers is
unchanged.

Projection cursor: `(transaction_id, position)` tuple, not bare position
------------------------------------------------------------------------
`StoredEvent.position` is a global commit-order watermark from a Postgres
`bigserial`. Sequences advance even on rolled-back transactions, and a
later-started transaction can commit before an earlier one. A naive
projection that polls `WHERE position > last_processed_position` will skip
events from a slow transaction that committed after a fast one with a
higher position.

The Phase-8e fix (added in migration `20260512240000_add_transaction_id`):
each event row carries a `transaction_id` (xid8 = 64-bit FullTransactionId,
monotonic, no wraparound; set by `DEFAULT pg_current_xact_id()` on INSERT,
never written from app code). Projection consumers advance via the
lexicographic tuple cursor:

    WHERE (transaction_id, position) > ($last_tx::xid8, $last_pos)
      AND transaction_id < pg_snapshot_xmin(pg_current_snapshot())
    ORDER BY transaction_id ASC, position ASC

The xid8 in-flight exclusion ensures we only consume events from
transactions that have FULLY committed; the tuple cursor preserves
ordering inside a single transaction (where one xid8 may span N events
with distinct positions). Pattern source: Khyst's postgresql-event-
sourcing reference + Dudycz's "Ordering in Postgres Outbox" article.

Combined with LISTEN/NOTIFY wake-up signal, polling can be infrequent.
Long-running transactions in the same database PAUSE all projections
until they commit (because `pg_snapshot_xmin` returns the lowest active
xid8); this is by design (correctness) but worth knowing operationally.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class NewEvent:
    """A domain event being written to the store. Wrapped at the app-layer boundary.

    `event_id` is the per-event stable identity (UUIDv7 in production via
    the IdGenerator port). It's the unit of downstream deduplication for
    at-least-once delivery to projections, and the natural value to use as
    the next command's `causation_id` in saga / process-manager chains.
    Generated in the handler (one per emitted event) so the decider stays
    pure and `cora.infrastructure.event_envelope.to_new_event` stays a
    dict-shuffle.

    `occurred_at` is domain time, set by the handler via the Clock port. The
    store also records its own `recorded_at` (DB write time) on persistence.

    `principal_id` is the UUID of the entity that pulled the trigger for
    this event (the authenticated caller; same value the handler received
    as its `principal_id` kwarg and the same one the Authorize port gated
    on). Day-1 hook for the future ReBAC graph projection (see
    `project_authz_future` memory). REQUIRED at the application-layer
    contract; the type stays `UUID | None` so callers can pass
    `None` to simulate historical pre-hook rows in tests, but pyright
    catches forgotten kwargs.
    Pre-hook events in storage stay legitimately None forever (no
    derivable historical value). Aligned with W3C PROV-O
    `prov:wasAssociatedWith.agent` at the envelope level; per-aggregate
    fields (Decision.actor_id) provide the domain-specific shapes
    layered above.

    The `field(kw_only=True)` on `principal_id` lets a no-default
    field follow the defaulted `causation_id` + `metadata` without
    violating dataclass field-ordering rules. Every existing caller
    constructs NewEvent with kwargs anyway, so there's no positional-
    arg breakage.
    """

    event_id: UUID
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    principal_id: UUID | None = field(kw_only=True)
    signature: bytes | None = field(default=None, kw_only=True)
    signature_kid: str | None = field(default=None, kw_only=True)
    signature_version: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class StoredEvent:
    """A domain event read from the store. Carries store-assigned metadata.

    `position` is the global commit-order watermark (`bigserial` from the DB).
    Use the `(transaction_id, position)` tuple as a projection cursor; see
    the module docstring for why position alone is unsafe.

    `transaction_id` is the Postgres `xid8` of the transaction that wrote
    this event (monotonic 64-bit, no wraparound). Set automatically by
    `DEFAULT pg_current_xact_id()` on INSERT; never written from app
    code. Returned as a Python `int`. Defaulted to 0 here so test
    fixtures that build StoredEvent directly stay terse; the two
    production adapters always set a real value.

    `event_id` is the producer-assigned identity (the same UUID supplied
    at append time in NewEvent.event_id). It is UNIQUE across the events
    table and serves as the dedup key for downstream consumers.

    `principal_id` is the UUID of the entity that pulled the trigger
    (the authenticated caller). Stays `None` forever for events written
    before the 9b-a hook landed; non-None for events written through the
    9b-b/C application-layer contract. The DB column is `NULL`-able by
    design: the past/future boundary lives at the column level, not in
    a backfill. See `NewEvent.principal_id` for the day-1-hook
    rationale.
    """

    position: int
    event_id: UUID
    stream_type: str
    stream_id: UUID
    version: int
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime
    recorded_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    transaction_id: int = 0
    principal_id: UUID | None = None
    signature: bytes | None = None
    signature_kid: str | None = None
    signature_version: str | None = None


class ConcurrencyError(Exception):
    """Raised when `expected_version` does not match the stream's current version."""

    def __init__(
        self,
        stream_type: str,
        stream_id: UUID,
        expected: int,
        actual: int,
    ) -> None:
        super().__init__(
            f"Optimistic concurrency conflict on stream "
            f"{stream_type}/{stream_id}: expected version {expected}, "
            f"found {actual}"
        )
        self.stream_type = stream_type
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class StreamAppend:
    """One stream's worth of events for `EventStore.append_streams`.

    Carries the same per-stream knobs as the single-stream `append`
    method (`stream_type` + `stream_id` + `expected_version` + `events`)
    so a caller can specify N streams of arbitrary types/ids in one
    atomic batch. Used by cross-aggregate slices like Safety's
    `amend_clearance` (parent's `ClearanceSuperseded` + child's
    `ClearanceRegistered`, both committed atomically or neither).
    """

    stream_type: str
    stream_id: UUID
    expected_version: int
    events: Sequence[NewEvent]


class EventStore(Protocol):
    """Append and load events with optimistic concurrency."""

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        """Load all events for a stream in order.

        Returns `(events, current_version)`. Returns `([], 0)` if the stream
        does not exist. Callers fold events with their evolver function.
        """
        ...

    async def append(
        self,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Sequence[NewEvent],
    ) -> int:
        """Append events with optimistic concurrency.

        Returns the new current version after append. Raises
        `ConcurrencyError` if `expected_version` does not match the stream's
        current version at the moment of write.
        """
        ...

    async def append_streams(
        self,
        streams: Sequence[StreamAppend],
        *,
        conn: object | None = None,
    ) -> dict[UUID, int]:
        """Atomically append events to multiple streams in a single transaction.

        All-or-nothing. If any stream's `expected_version` does not match,
        the entire batch rolls back: no events from any stream become
        visible. Raises `ConcurrencyError` for the first offending stream.

        Returns a `dict` keyed by `stream_id` whose values are the new
        current version per stream after the append.

        Used by cross-aggregate atomic writes (Safety's `amend_clearance`
        is the first consumer: parent's `ClearanceSuperseded` + child's
        `ClearanceRegistered` must commit together or not at all).

        Streams may share or differ in `stream_type`. Same `event_id`
        UNIQUE constraint as `append` (raises `ValueError` /
        `UniqueViolationError` on duplicate event_id within or across
        streams in the same batch).

        `conn` (optional, asyncpg.Connection): when provided, runs the
        appends against that connection without opening a nested
        transaction — used by `forget_actor` to bundle the event
        append with a `ProfileStore.scrub_and_delete` call in ONE
        Postgres transaction so the PII scrub + audit event commit
        atomically. When `None`, the adapter acquires its own
        connection and transaction (the default for every other
        caller). Typed as `object | None` so the Protocol stays
        asyncpg-agnostic; InMemoryEventStore ignores the parameter.
        """
        ...
