"""Composition-root (`cora.api`) application errors.

Errors raised by the composition-root runtimes (the watcher agents and their
shared scaffold) live here rather than inside a runtime module, mirroring the
per-BC `cora/<bc>/errors.py` convention so the `*Error` suffix has a home that
test_domain_errors_in_state_module accepts (a runtime module is not an exempt
location; an `errors.py` is).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class WatcherReadUnauthorizedError(Exception):
    """A watcher's authz-gated read (its list drain or a per-candidate lookup)
    was Denied.

    Each watcher's tick wraps the BC-local `UnauthorizedError` its read raises
    into this scaffold-owned type so the shared `_watch_loop` can tell a
    READ-denial -- a misconfigured grant that silently BLINDS the watchdog (the
    worse-than-none failure) -- apart from a generic tick failure, and surface it
    as a distinct, loud, edge-triggered warning instead of a buried traceback.
    The scaffold cannot catch the BC error directly: each BC raises its own
    (deliberately un-hoisted) `UnauthorizedError`, so the per-watcher tick does
    the wrap, and the scaffold owns the one shared type. Reused for the
    strict-mode startup probe (a fail-fast boot refusal carries the same shape).

    A composition-root control-flow signal, not a domain error, so it lives in
    `cora/api/errors.py` (not an aggregate kernel) but keeps the `*Error` suffix.
    """

    def __init__(self, *, query_name: str, principal_id: UUID, reason: str) -> None:
        super().__init__(f"watcher read {query_name} denied: {reason}")
        self.query_name = query_name
        self.principal_id = principal_id
        self.reason = reason


__all__ = ["WatcherReadUnauthorizedError"]
