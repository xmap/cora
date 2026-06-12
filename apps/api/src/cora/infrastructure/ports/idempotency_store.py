"""Idempotency-Key port: cache `(principal_id, key, surface_id) -> claim outcome`.

Implements the IETF `Idempotency-Key` header pattern (Stripe / Adyen /
PayPal style; tracks
[draft-ietf-httpapi-idempotency-key-header](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header)).
The application-layer decorator
`cora.infrastructure.idempotency.with_idempotency` wraps a command
handler: on retry with the same key, the cached outcome is returned
without re-executing the command.

The cache namespace is `(principal_id, key, surface_id)` per IETF
§5 server-side composite-key recommendation. `surface_id` belongs
in the tuple because under V2 per-surface policies a retry from a
different Surface must re-authorize, so each Surface gets an
independent cache slot. The decorator threads surface_id from the
HTTP/MCP resolver (`get_surface_id` / `get_mcp_surface_id`) all the
way down to `claim()`.

## Two-phase claim + 4xx error caching

The richer surface captures the full claim lifecycle (vs a naive
single-phase `get + put`):

  - `claim()` is the only entry point. Atomically tries to win the
    in-flight lock for `(principal_id, key)`. Returns one of five
    outcomes:
      - `Claimed` — won the race, run the handler, then call
        `finalize_success()` or `finalize_error()`.
      - `CachedSuccess` — a previous handler invocation succeeded
        with the SAME command_hash; return the cached result.
      - `CachedError` — a previous handler invocation raised a
        cacheable 4xx error with the SAME command_hash; raise
        `CachedHandlerError` so the response replays.
      - `LockedRecent` — another in-flight request holds the lock
        (recently enough to not be stale); raise
        `IdempotencyClaimLostError` -> 409 + Retry-After: 1.
      - `HashConflict` — same key reused with a DIFFERENT command
        body; raise `IdempotencyConflictError` -> 422.
  - `finalize_success(principal_id, key, result)` clears `locked_at`
    and stores the JSON-serializable result.
  - `finalize_error(principal_id, key, error_type, error_msg)` clears
    `locked_at` and stores the cached error so future retries
    replay it.
  - `prune(ttl_hours)` deletes completed rows older than the TTL.
    Called periodically by the pruner background task.

## Stale-lock recovery

If a worker crashes mid-handler, its row stays locked. The `claim()`
implementation atomically takes over locks older than
`lock_stale_seconds` (passed by the decorator from settings). No
janitor thread needed; recovery happens on the next claim attempt.

## 4xx caching scope (intentional)

Only domain errors mapped to 4xx are cached. 5xx (server / infra
failures) are never cached: a transient infra blip should not
permanently lock a key into a failure state. The event-sourcing
optimistic-lock backstop (`event_store.append(expected_version=...)`)
protects state integrity for any retry that does sneak through.

## Cached results format

Cached results are JSON-serializable forms of the handler's return
value (UUIDs become str, None stays null). Callers of the decorator
provide per-handler serialize/deserialize callables.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class Claimed:
    """We won the claim race. Handler runs next."""


@dataclass(frozen=True)
class CachedSuccess:
    """A previous invocation succeeded with the same command_hash."""

    command_hash: str
    command_name: str
    result: Any
    """JSON-serializable form of the handler's return value."""


@dataclass(frozen=True)
class CachedError:
    """A previous invocation raised a cacheable 4xx with the same command_hash."""

    command_hash: str
    command_name: str
    error_type: str
    """Fully-qualified exception class name, for example,
    `cora.access.aggregates.actor.InvalidActorNameError`."""
    error_msg: str
    """`str(exc)` of the original exception."""


@dataclass(frozen=True)
class LockedRecent:
    """Another in-flight request holds the lock (still within stale window)."""

    locked_at: datetime
    """Diagnostic; lets the decorator (or future tuning) compute how
    much longer until the lock would be considered stale."""


@dataclass(frozen=True)
class HashConflict:
    """Same key reused with a DIFFERENT command body. Client bug."""

    expected_hash: str
    """Hash of the command body the cached row was created with."""
    actual_hash: str
    """Hash of the command body just submitted."""


type ClaimOutcome = Claimed | CachedSuccess | CachedError | LockedRecent | HashConflict


class IdempotencyConflictError(Exception):
    """Same Idempotency-Key reused with a different command body.

    Per the IETF draft this is a client bug (a key MUST be tied to a
    single logical request). Mapped to HTTP 422 by the BC's exception
    handler.
    """

    def __init__(
        self,
        key: str,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        super().__init__(
            f"Idempotency-Key {key!r} was previously used with a different "
            f"request body (expected hash {expected_hash[:12]}..., "
            f"got {actual_hash[:12]}...)"
        )
        self.key = key
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class IdempotencyClaimLostError(Exception):
    """Race lost: another request holds the in-flight lock for this key.

    Mapped to HTTP 409 + `Retry-After: 1` header by the global
    handler in `cora.access.routes`. Standard HTTP retry-after
    semantics: clients (most SDKs) auto-retry after the indicated
    delay.
    """

    def __init__(self, key: str, locked_at: datetime) -> None:
        super().__init__(
            f"Idempotency-Key {key!r} is locked by another in-flight request "
            f"(claimed at {locked_at.isoformat()}); retry after delay"
        )
        self.key = key
        self.locked_at = locked_at


class CachedHandlerError(Exception):
    """A previous handler invocation raised a cacheable domain error.

    The route layer reconstructs the appropriate HTTP response from
    the cached `error_type` and `error_msg` via the convention-based
    classifier. Mapped per-classifier-result by the global handler in
    `cora.access.routes`.
    """

    def __init__(self, error_type: str, error_msg: str) -> None:
        super().__init__(f"{error_type}: {error_msg}")
        self.error_type = error_type
        self.error_msg = error_msg


class IdempotencyStore(Protocol):
    """Storage for `(principal_id, key, surface_id) -> outcome` records.

    See module docstring for the full claim lifecycle.
    """

    async def claim(
        self,
        principal_id: UUID,
        key: str,
        surface_id: UUID,
        command_hash: str,
        command_name: str,
        *,
        lock_stale_seconds: int,
    ) -> ClaimOutcome:
        """Atomically attempt to win the in-flight lock for the key.

        Returns one of `Claimed | CachedSuccess | CachedError |
        LockedRecent | HashConflict`. Stale locks (older than
        `lock_stale_seconds`) are atomically taken over and reported
        as `Claimed` (recovery from crashed workers).
        """
        ...

    async def finalize_success(
        self,
        principal_id: UUID,
        key: str,
        surface_id: UUID,
        result: Any,
    ) -> None:
        """Clear `locked_at` and store the success result. The row
        was previously claimed by `claim()` returning `Claimed`.

        Caller contract: `result` MUST be JSON-serializable AND
        MUST NOT be `None`. The PG adapter's CHECK constraint
        requires `(locked_at IS NULL AND result IS NOT NULL)` for
        the completed-success row state; passing `result=None`
        would either violate the constraint (PG) or leave the row
        in an unreachable tri-state (memory). Handlers that
        legitimately return `None` should serialize to a sentinel
        (for example `serialize_result=lambda _: "ok"`) at wire time.
        """
        ...

    async def finalize_error(
        self,
        principal_id: UUID,
        key: str,
        surface_id: UUID,
        error_type: str,
        error_msg: str,
    ) -> None:
        """Clear `locked_at` and store the cached error so future
        retries replay it. The row was previously claimed by
        `claim()` returning `Claimed`.

        Caller contract: both `error_type` and `error_msg` MUST be
        non-empty strings. The PG adapter's CHECK constraint
        requires `(locked_at IS NULL AND error_type IS NOT NULL
        AND error_msg IS NOT NULL)` for the completed-error row
        state. The decorator always passes `_full_class_name(exc)`
        and `str(exc)` which are non-empty by construction.
        """
        ...

    async def prune(self, *, ttl_hours: int) -> int:
        """Delete completed rows older than `ttl_hours`. Returns the
        number of rows deleted. Called periodically by the pruner
        background task."""
        ...
