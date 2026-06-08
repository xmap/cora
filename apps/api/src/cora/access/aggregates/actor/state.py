"""Actor aggregate state, value objects, and domain errors.

`Actor` is the aggregate root for the Access BC. The aggregate carries
no PII -- human-facing display data lives in the `actor_profile` table
per [[project_pii_vault]] / [[project_pii_vault_implementation_design]].
`ActorName` is a write-time value object that validates the display-
name invariants (1-200 chars, trimmed) before the handler passes the
string to `ProfileStore.upsert`; it is NOT part of aggregate state.

All errors raised by the domain layer are `Exception` subclasses
defined here so callers can catch them by type.

## Additive evolution: `kind` field

`Actor.kind` discriminates `human` from `agent` Actors. Per
[[project_agent_bc_design]], every Agent in the Agent BC has a
corresponding Actor in Access BC sharing the same `id`, with
`kind="agent"`; the cross-BC atomic write in `define_agent` emits
both `ActorRegistered(kind="agent")` and `AgentDefined` in one
transaction.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import bounded_name

ACTOR_NAME_MAX_LENGTH = 200


class ActorKind(StrEnum):
    """Discriminates human / agent / service-account Actors.

    Three values:

      - `human` -- registered via `register_actor` (Access BC).
                   Default for legacy Actor streams (forward-compat).
      - `agent` -- registered via `define_agent` (Agent BC) as part
                   of the cross-BC atomic write.
      - `service_account` -- registered via `register_actor(kind=...)`
                   for machine callers (CI bridges, autonomous agent
                   runtime processes, future TomoScan/EPICS bridges).
                   Aligns with the closed set on
                   `cora.infrastructure.ports.token_verifier.PrincipalKind`
                   which carries the same closed set on the edge-auth
                   side. Service-account Actors are functionally
                   identical to humans at the Authorize port; the
                   discriminator exists for forensic logging + policy
                   shapes that want to scope machine callers separately
                   (for example "this Policy allows only kind=service_account
                   callers from issuer=internal-ci.example.com").

    Decision.actor_id semantics survive the split: humans, agents, and
    service accounts are all first-class principals through the same
    Authorize port per [[project_architecture]], so `actor_id` reference
    checks work uniformly without polymorphism.
    """

    HUMAN = "human"
    AGENT = "agent"
    SERVICE_ACCOUNT = "service_account"


class InvalidActorNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Actor name must be 1-{ACTOR_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidActorKindError(ValueError):
    """The supplied kind is not permitted for this registration path.

    Raised by the `register_actor` decider when kind=AGENT is passed.
    Agent-kind Actors come exclusively from the cross-BC atomic write
    in `define_agent` per [[project_agent_bc_design]] P0-4.

    Maps to HTTP 400 via the route-layer exception handler's
    `Invalid*Error`-class convention. The message is redacted (no
    internal-architecture detail leak) so 500-fallback-to-default-FastAPI
    body would not expose the P0-4 lock rationale to non-HTTP callers.
    """

    def __init__(self, kind: str) -> None:
        super().__init__(f"register_actor cannot mint kind={kind!r} Actors via this route.")
        self.kind = kind


class ActorAlreadyExistsError(Exception):
    """Attempted to register an actor whose stream already has events."""

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} already exists")
        self.actor_id = actor_id


class ActorNotFoundError(Exception):
    """Attempted an operation on an actor whose stream has no events."""

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} not found")
        self.actor_id = actor_id


class ActorCannotDeactivateError(Exception):
    """Attempted to deactivate an actor that is already deactivated."""

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Actor {actor_id} is already deactivated")
        self.actor_id = actor_id


@bounded_name(max_length=ACTOR_NAME_MAX_LENGTH, error_class=InvalidActorNameError)
@dataclass(frozen=True)
class ActorName:
    """Display name for an actor. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class Actor:
    """Aggregate root: an identified principal known to CORA.

    Carries NO PII. Display name and future PII fields (email, phone,
    ORCID, affiliation) live in the `actor_profile` table; read paths
    compose the display surface via `load_actor_display_name` from
    `cora.access.aggregates.actor.profile`.

    `active` defaults to True at construction; the evolver sets it
    explicitly when folding ActorRegistered (active) and ActorDeactivated
    (inactive). `kind` defaults to `ActorKind.HUMAN`; legacy
    ActorRegistered V1 events lacking the field fold to the default
    via `payload.get("kind", "human")` in `from_stored`.
    """

    id: UUID
    active: bool = True
    kind: ActorKind = ActorKind.HUMAN
