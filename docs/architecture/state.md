# State

*Envelope, invariants, read models.*

Every state change emits an immutable event; aggregate state is rebuilt by folding the stream. The store is the system of record; current state is a derived view. For the storage pick and wire-format specifics, see [Stack/Data](../stack/data.md).

## Envelope

Every event has two halves. The **envelope** carries identity, ordering, and audit:

| Field | Role |
| --- | --- |
| event id | event (dedup key for subscribers) |
| stream type | aggregate kind (subscriber routing) |
| stream id | aggregate instance |
| event type | fact class (routing, schema evolution) |
| per-stream version | order within stream (optimistic concurrency on append) |
| global ordering position | order across store (projection cursor) |
| principal id | emitter (audit, future ReBAC hook) |
| occurred at | wall-clock time of emission |

The **payload** carries the change. Primitives only; the evolver re-validates by reconstructing value objects on read (see [Reference/Modeling](../reference/modeling.md)).

Subscribers route on `(stream type, event type)` and dedupe on event id.

## Invariants

<div class="cora-aside" markdown>

- **Append-only at the storage layer.** Immutability is enforced where state lives, not in application code; the application identity cannot mutate or remove existing events.
- **Gap-free ordering for cursors.** Projection workers advance against committed transactions only; in-flight writes never appear ahead of older ones.
- **Optimistic concurrency by version.** Writers assert the expected per-stream version on append; a mismatch fails the transaction. No advisory locks, no last-write-wins.

</div>

## Read models

Reads are not the inverse of writes. The write path goes through a decider and emits events; the read path projects off them, with no decider and no new events.

<div class="cora-aside" markdown>

- **Fold-on-read.** Single-aggregate read replays the aggregate's stream on every request. Cost grows with stream length; no snapshots yet.
- **Projection workers.** List, filter, search. Background processes tail the store, maintain a per-projection denormalised table, and advance a bookmark. Per-projection logic plugs into a generic registry.

</div>

### Where lifecycle timestamps live

Wall-clock timestamps (`created_at`, `versioned_at`, `deprecated_at`) belong on projections, not aggregate state. The envelope's `occurred_at` is the source of truth; projections derive timestamp columns from it as events arrive. State stays narrow and concerned with invariants; the read side answers "when did X happen?" by joining the projection row.

Shipped across Method, Plan, Practice, Capability, Family, and Agent (Path C). The Surface aggregate goes one step further and carries no lifecycle timestamps at all: they're rarely useful for an immutable config-time registry.
