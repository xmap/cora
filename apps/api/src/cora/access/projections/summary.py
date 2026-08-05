"""ActorSummaryProjection: folds Actor lifecycle events into the
`proj_access_actor_summary` read model that backs `GET /actors`.

Subscribed events:
  - ActorRegistered (V1 legacy) -> INSERT a row at status='active'
    with the payload-carried `name`.
  - ActorRegisteredV2 -> INSERT a row at status='active' with name
    pulled from the `actor_profile` PII vault (the writer upserts
    the profile row BEFORE appending the V2 event, so the row is
    always visible by the time the projection applies).
  - ActorDeactivated -> UPDATE status to 'deactivated'.
  - ActorReactivated -> UPDATE status back to 'active'. The
    inverse of the line above, so a deactivation that was issued
    in error leaves no permanent mark on the read model.
  - ActorProfileForgotten -> UPDATE the cached display name to the
    tombstone literal so list reads see "<deleted user>" without
    a JOIN against actor_profile. The audit event records WHEN the
    erasure happened; the projection rewrites the read-side cached
    display surface to match the post-erasure actor_profile state.

Every apply branch is idempotent (the framework delivers at-least-
once; re-applying the same event must produce the same row state):

  - INSERT uses `ON CONFLICT (actor_id) DO NOTHING` so re-application
    of the same registration event is a no-op.
  - UPDATEs write the same target value regardless of how many times
    the event lands; idempotent by construction.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.access.aggregates.actor import DELETED_ACTOR_DISPLAY_NAME
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ACTOR_SQL = """
INSERT INTO proj_access_actor_summary
    (actor_id, name, kind, status, created_at)
VALUES ($1, $2, $3, 'active', $4)
ON CONFLICT (actor_id) DO NOTHING
"""

# V2 INSERT pulls `name` from actor_profile (PII vault). The vault
# row is written before the V2 event commits (see register_actor and
# define_agent handlers); the LEFT JOIN style guards against the
# theoretical case where the row was already erased between event
# emit and projection apply, falling back to empty string so the
# NOT NULL constraint still holds. The list_actors handler is the
# eventual reader; Commit 5 swaps it to JOIN actor_profile so the
# projection's stored `name` becomes a fallback for legacy rows.
_INSERT_ACTOR_V2_SQL = """
INSERT INTO proj_access_actor_summary
    (actor_id, name, kind, status, created_at)
SELECT $1, COALESCE(ap.name, ''), $2, 'active', $3
FROM (SELECT 1) AS one
LEFT JOIN actor_profile ap ON ap.actor_id = $1
ON CONFLICT (actor_id) DO NOTHING
"""

_DEACTIVATE_ACTOR_SQL = """
UPDATE proj_access_actor_summary
SET status = 'deactivated', updated_at = now()
WHERE actor_id = $1
"""

_REACTIVATE_ACTOR_SQL = """
UPDATE proj_access_actor_summary
SET status = 'active', updated_at = now()
WHERE actor_id = $1
"""

# Post-erasure tombstone: overwrite the cached display name with the
# locale-neutral English literal. Idempotent: repeated applies set the
# same value. WHERE actor_id = $1 makes it a no-op if the row is
# absent (race-tolerant: an out-of-order ActorProfileForgotten before
# ActorRegistered* would silently do nothing rather than insert a
# tombstone row out of thin air).
_FORGET_ACTOR_SQL = """
UPDATE proj_access_actor_summary
SET name = $2, updated_at = now()
WHERE actor_id = $1
"""


class ActorSummaryProjection:
    """Maintains the `proj_access_actor_summary` read model.

    `name` and `subscribed_event_types` are class-level constants
    (not ClassVar-annotated, matching the Projection Protocol's
    plain-attr declaration). Python semantics are identical to
    ClassVar for these immutable values.
    """

    name = "proj_access_actor_summary"
    subscribed_event_types = frozenset(
        {
            "ActorRegistered",
            "ActorRegisteredV2",
            "ActorDeactivated",
            "ActorReactivated",
            "ActorProfileForgotten",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        """Dispatch on event_type. All branches are idempotent.

        The worker's advance query filters by
        `event_type = ANY($subscribed_event_types)` so apply() never
        sees unsubscribed types in production. The bare `case _: pass`
        below is for pyright exhaustiveness on `str`, not defensive
        runtime logic — a future projection author who adds an event
        type to `subscribed_event_types` without adding a match arm
        will see missing rows in the projection table (loud and easy
        to debug), not silent corruption.
        """
        match event.event_type:
            case "ActorRegistered":
                # Legacy V1: payload carries `name`. `kind` is
                # forward-compat: the oldest legacy payloads lack
                # it, matching `from_stored`'s default of "human".
                await conn.execute(
                    _INSERT_ACTOR_SQL,
                    UUID(event.payload["actor_id"]),
                    event.payload["name"],
                    event.payload.get("kind", "human"),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "ActorRegisteredV2":
                # Post-PII-vault: payload carries no `name`; pull it
                # from actor_profile via sub-SELECT.
                await conn.execute(
                    _INSERT_ACTOR_V2_SQL,
                    UUID(event.payload["actor_id"]),
                    event.payload["kind"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "ActorDeactivated":
                await conn.execute(
                    _DEACTIVATE_ACTOR_SQL,
                    UUID(event.payload["actor_id"]),
                )
            case "ActorReactivated":
                await conn.execute(
                    _REACTIVATE_ACTOR_SQL,
                    UUID(event.payload["actor_id"]),
                )
            case "ActorProfileForgotten":
                # Rewrite the cached display name in place; the actor
                # row itself stays on the projection (the
                # pseudonymised actor_id reference remains valid per
                # EDPB 01/2025 Example 10). Status / kind / created_at
                # are unchanged.
                await conn.execute(
                    _FORGET_ACTOR_SQL,
                    UUID(event.payload["actor_id"]),
                    DELETED_ACTOR_DISPLAY_NAME,
                )
            case _:
                pass


__all__ = ["ActorSummaryProjection"]
