"""PrincipalLivenessLookup port: is the calling principal switched on?

Every principal CORA knows has an `Actor` in the Access BC, including
agents (`Agent.id == Actor.id` by the cross-BC genesis invariant). So
`Actor.active` is one fact that describes a human and an agent
identically, and this port exposes it to callers that cannot import
Access.

## Why a port rather than a direct read

`cora.trust` declares `depends_on = ["cora.infrastructure",
"cora.shared", "cora.trust.aggregates"]` and holds zero `from
cora.access` imports. The decision point resolving liveness for itself
is the correct shape (see `cora.trust._authorization_decision`), but it
must not widen the module graph to get there. This port is the same
seam ~20 sibling lookups already use.

## The asymmetry this exists to close

A suspended Agent genuinely stops acting: three sites check
`AgentStatus.VERSIONED` before invoking one, and `_ratification_shared`
calls `load_actor().active` "the same operator-deactivation revocation
surface every sibling agent uses". A deactivated HUMAN is stopped
almost nowhere, because the authorization gate never reads the flag. So
today an operator who deactivates a person has not removed their
permissions, only their ability to be invoked as an agent. Deactivating
software works; deactivating a person is close to decorative.

## Three-valued on purpose

`Actor | None` from `load_actor` already carries the distinction, and
collapsing it to a boolean would lose the half that matters for a
legible denial: an UNREGISTERED principal and a DEACTIVATED one need
different remedies (register them versus reactivate them). A gate that
says only "no" teaches an operator nothing at 3am.

`Settings.liveness_posture` governs what the gate does with the answer:
"off" never reads it, "shadow" resolves and logs without denying, and
"enforce" refuses a principal that is not active. Shadow exists so the
measurement (how many live requests would enforcement have refused, and
which remedy each needed) can precede the refusals, per the
observe-then-enforce discipline the human-envelope design requires.
"""

from enum import StrEnum
from typing import Protocol
from uuid import UUID


class PrincipalLiveness(StrEnum):
    """Whether a principal is registered, and whether it is switched on.

    Three values:

      - `Active`       -- an Actor exists and `active` is True.
      - `Deactivated`  -- an Actor exists and an operator turned it
                          off. Remedy is `reactivate_actor`.
      - `Unregistered` -- no Actor stream exists for this principal.
                          Remedy is `register_actor`.

    `Unregistered` is NOT an error condition on its own. Under
    `AllowAllAuthorize` (the documented bootstrap workflow) commands run
    before any Actor exists, and a bearer-mode deployment resolves
    principals through a subject map that may name an Actor id before
    the Actor is registered. Whether it should refuse a request is a
    policy question this port deliberately does not answer.
    """

    ACTIVE = "Active"
    DEACTIVATED = "Deactivated"
    UNREGISTERED = "Unregistered"


class PrincipalLivenessLookup(Protocol):
    """Resolve one principal's liveness."""

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness: ...


class AlwaysLivePrincipalLivenessLookup:
    """No-op stub: every principal reads `Active`.

    Sibling of `AllowAllAuthorize` and `AlwaysCoveredClearanceLookup`,
    and used for the same reasons: tests and dev wiring that do not care
    about liveness, plus the bootstrap workflow where Actors do not
    exist yet.

    Contract drift versus the real adapter is deliberate and total: this
    stub cannot distinguish the three values, so a test that asserts on
    `Deactivated` or `Unregistered` must wire a real lookup or a fake
    that returns them. Anything that passes under this stub has proven
    nothing about liveness.
    """

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        _ = principal_id
        return PrincipalLiveness.ACTIVE


__all__ = [
    "AlwaysLivePrincipalLivenessLookup",
    "PrincipalLiveness",
    "PrincipalLivenessLookup",
]
