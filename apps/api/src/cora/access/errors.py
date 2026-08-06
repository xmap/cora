"""BC-application-layer errors for the Access BC.

These errors are raised by application handlers (not domain logic) and
mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/access/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/actor/state.py`.

Distinct class from `cora.subject.errors.UnauthorizedError` /
`cora.trust.errors.UnauthorizedError`: each BC owns its own
application-error namespace so an Access 403 is distinguishable
from a Subject or Trust 403 in logs / aggregator filters
(documented in CONTRIBUTING.md "BC-application-layer errors").
Cross-BC consumers catching authorization failures import per-BC.
"""

from typing import ClassVar
from uuid import UUID


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ActorSelfReactivationRefusedError(Exception):
    """A principal attempted to reinstate its own deactivated Actor.

    Lives here, beside `UnauthorizedError`, rather than in the Actor
    aggregate's error block. The `<X>Cannot<Verb>Error` names there are
    the 409 state-transition family (`ActorCannotDeactivateError`,
    `ActorCannotReactivateError`): they mean the aggregate is in the
    wrong state for the command. This one is a 403. The aggregate is in
    exactly the right state to be reactivated; what is refused is WHO
    asked. Filing it with the transition errors would have put an
    authority refusal in the family a reader scans for state conflicts.

    Refused structurally rather than by Policy configuration. The gate's
    liveness conjunct fails OPEN on a lookup error by design, so without
    this the only barrier to self-reinstatement is a check built to
    yield under fault. Granting `ReactivateActor` means the power to
    reinstate colleagues; self-reinstatement is a different power and
    nobody would expect it to ride along.
    """

    # Without this the idempotency layer's `classify_error_status` would
    # fall through to its 409 default, because the old name was in the
    # `<X>Cannot<Verb>Error` state-conflict family and this one matches no
    # branch. Inert today (`reactivate_actor` is not idempotency-wrapped),
    # declared anyway so wrapping it later cannot quietly downgrade an
    # authority refusal into a state conflict.
    idempotency_http_status: ClassVar[int] = 403

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} cannot reactivate itself")
        self.actor_id = actor_id
