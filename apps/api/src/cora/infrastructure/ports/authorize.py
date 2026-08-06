"""Authorize port: gate every command behind authz.authorize(principal, command, conduit, surface).

`principal_id` (not `actor_id`) names the invoker because the Access BC
already owns an `Actor` aggregate; using `actor_id` for both the Actor
aggregate's id and the calling-party's id was a real bug vector at
handler call sites where commands target an Actor aggregate (for example,
DeactivateActor).

`conduit_id: UUID` names the ISA-99/IEC-62443 inter-zone
channel — comms path between two trust zones — through which the
command would flow. Operationally inert at v1: every handler passes
`UUID(int=0)` nil-sentinel. Reactivation tracked as
project_conduit_injection_design.md WI10.

`surface_id: UUID` names the process-level arrival point (HTTP /
MCP stdio / MCP streamable-http) through which the request entered
CORA. Closed-StrEnum kind sits on the
`cora.trust.aggregates.surface.Surface` aggregate; surface adapters
resolve concrete IDs per request, and edge-auth layers OAuth `aud`
validation on top.

Defaults: both `conduit_id` and `surface_id` default to nil
`UUID(int=0)` so existing handler call sites work unchanged. As real
routing arrives at the HTTP / MCP / A2A boundaries, routes inject
concrete IDs and stop using the nil sentinel — the architecture
fitness test pins the no-nil-leak invariant.

`AllowAllAuthorize` is the no-op stub used for dev/test and the
documented bootstrap workflow; `TrustAuthorize`
(in `cora.trust.authorize`) is the production adapter.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from cora.infrastructure.routing import NIL_SENTINEL_ID


class Conjunct(StrEnum):
    """A named input an authorization decision consulted.

    Stamped on every result as `evaluated`, so a decision reports which
    questions it actually answered instead of leaving that to the
    reader's assumption. A caller that consults fewer conjuncts than the
    gate produces a partial answer, and this set is what makes the
    partiality legible in a log, a test, or an API response rather than
    a convention someone has to remember.

      - `Policy` -- the Policy aggregate's conduit, surface,
                    permitted-principal, and permitted-command predicate
      - `Liveness` -- whether the calling principal is a registered
                    Actor that an operator has not switched off. Reads
                    `Actor.active`, one fact that describes a human and
                    an agent identically because `Agent.id == Actor.id`.

    Members are added as conjuncts land, never ahead of them. An
    unpopulated member would let a result claim it evaluated something
    no code checks, which is the one failure this vocabulary exists to
    make impossible.

    A member appearing in `evaluated` means the decision CONSULTED it,
    not that the deployment has it wired. `Liveness` is absent when the
    posture is "off" or "shadow", when the command is exempt, or when
    the read failed, so an absence distinguishes "never asked" from
    "asked and passed".

    That distinction lives on the RESULT and nowhere else today: the
    `Verdict` entry row has no conjunct column, so `evaluated` is not
    persisted. Do not describe the verdict logbook as recording which
    conjuncts ran until it carries them.
    """

    POLICY = "Policy"
    LIVENESS = "Liveness"


@dataclass(frozen=True)
class Allow:
    """Authorization granted.

    `evaluated` names the conjuncts the decision consulted to get here.
    It defaults to empty because a stand-in that decides on nothing
    (`AllowAllAuthorize`) should say so: an empty set is the honest
    report for a permissive fallback, and it is what distinguishes that
    fallback from a real grant in a verdict record.
    """

    evaluated: frozenset[Conjunct] = frozenset()


@dataclass(frozen=True)
class Deny:
    """Authorization denied with a reason.

    `evaluated` carries the same meaning as on `Allow`: the conjuncts
    consulted, including the one that refused.
    """

    reason: str
    evaluated: frozenset[Conjunct] = frozenset()


type AuthzResult = Allow | Deny


class Authorize(Protocol):
    """Authorization gate: called before every command.

    Named-method (not `__call__`) per Python typing-community guidance
    (PEP 544 + typing spec + mypy docs): `__call__` Protocols are for
    callback signatures `Callable[...]` can't express (variadic,
    overloaded, complex generic). A single-operation domain port uses
    a regular method, matching CORA's other ports (`Clock.now`,
    `EventStore.load`, `TokenVerifier.verify`, …) and the broader
    authorization-library corpus (Spring Security 6's
    `AuthorizationManager.authorize`, Pundit's `authorize`, Cedar's
    `is_authorized`, Casbin's `enforce`).

    The seam: `Kernel.authz: Authorize` with call sites reading
    `await deps.authz.authorize(...)` — "use the authz port to
    authorize this command." Factory protocols (`AuthorizeFactory`,
    `LLMFactory`) DO use `__call__` because they ARE construction
    functions; this port is not.
    """

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult: ...


class AllowAllAuthorize:
    """No-op stub: returns Allow for every call.

    Production wiring uses `cora.trust.authorize.TrustAuthorize`;
    AllowAll remains for tests/dev and the documented bootstrap
    workflow (define the gating policy under AllowAll, then restart
    with TrustAuthorize wired against it).
    """

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id, surface_id)
        return Allow()
