"""Pure decider for the `ReactivateActor` command.

Update-style decider: receives the rebuilt `Actor` state (folded from
the loaded event stream) and returns the events to append. No I/O.

Invariants:
  - State must not be None (actor must exist) -> ActorNotFoundError
  - Caller must not be the target (nobody reinstates themselves)
    -> ActorSelfReactivationRefusedError
  - State must be inactive (no reactivating a live actor)
    -> ActorCannotReactivateError

The self check is ordered BEFORE the already-active one on purpose. Were
it second, asking about your own Actor would return a different error
depending on whether you were switched off, turning the error type into
a probe for your own liveness.

## Why this slice exists

An Agent holds a reversible operator pause: `suspend_agent` is undone
by `resume_agent`. Before this slice an Actor's pause was one-way,
because `deactivate_actor` had no counterpart, so a mis-issued
deactivation left the person locked out with no remedy inside the
system. That is the lockout shape the authorization design refuses
everywhere else, and it applied more harshly to people than to
software. The two principal kinds now hold the same switch.

## What reactivation does NOT do

It restores availability and nothing else. Policy membership, grants,
and every other narrowing are untouched, so an actor reactivated into
a Policy that no longer names them remains unable to act. Keeping the
event this narrow is what lets it stay unauthored by any reason text:
it asserts only that the actor is available again.

## Deployment note: the pair must be granted together

Nothing here can enforce it, because `permitted_commands` is operator
authored at runtime rather than seeded (the bootstrap Policy grants
only `DefinePolicy` and `RegisterActor`). A deployment that grants
`DeactivateActor` without `ReactivateActor` still has a one-way pause,
just relocated from the domain into its Policy. Grant them together.

## Orthogonality with agent-kind Actors

Mirrors `deactivate_actor`: this accepts ANY Actor regardless of
`kind`, and the Actor's `active` flag stays orthogonal to the Agent
aggregate's own lifecycle. Reactivating an agent-kind Actor lifts the
soft pause; it does not resurrect an Agent whose status is Deprecated,
which remains the hard end-of-life signal.
"""

from datetime import datetime
from uuid import UUID

from cora.access.aggregates.actor import (
    Actor,
    ActorCannotReactivateError,
    ActorNotFoundError,
    ActorReactivated,
)
from cora.access.errors import ActorSelfReactivationRefusedError
from cora.access.features.reactivate_actor.command import ReactivateActor


def decide(
    state: Actor | None,
    command: ReactivateActor,
    *,
    now: datetime,
    principal_id: UUID,
) -> list[ActorReactivated]:
    """Decide the events produced by reactivating a deactivated actor.

    `principal_id` is here for one refusal: nobody reinstates themselves.
    Without it, the only thing standing between a deactivated principal
    and its own reinstatement is the liveness conjunct at the gate, and
    that conjunct fails OPEN on a lookup error by design. One induced
    read failure would then be enough to persist `ActorReactivated` on
    your own stream, and an event already written is not undone by the
    warning that accompanied it.

    Structural rather than delegated to Policy: an operator who grants
    `ReactivateActor` to a team is granting the power to reinstate
    colleagues, and would not expect it to include self-reinstatement.
    Making that unrepresentable is cheaper than expecting every
    deployment's policy to carve it out correctly.
    """
    if state is None:
        raise ActorNotFoundError(command.actor_id)
    if state.id == principal_id:
        raise ActorSelfReactivationRefusedError(state.id)
    if state.active:
        raise ActorCannotReactivateError(state.id)
    return [ActorReactivated(actor_id=state.id, occurred_at=now)]
