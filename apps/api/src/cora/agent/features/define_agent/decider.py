"""Pure decider for the `DefineAgent` command.

Pure function: given the current Agent state (None for a fresh
stream) and a `DefineAgent` command, returns the events to append
on the Agent stream. No I/O, no awaits, no side effects.

The CROSS-BC `ActorRegistered(kind="agent")` event on the Access
stream is built directly by the handler (not by this decider) and
written atomically alongside the `AgentDefined` event via
`EventStore.append_streams`. Decider stays focused on the Agent BC's
domain invariants.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle: capture,
don't recompute).

## Validation

  - State must be None (genesis-only) -> `AgentAlreadyExistsError`
  - `kind` wrapped via `AgentKind(...)`; 1-100 chars after trim ->
    `InvalidAgentKindError`
  - `name` wrapped via `AgentName(...)`; 1-100 chars after trim ->
    `InvalidAgentNameError`
  - `version` wrapped via `AgentVersion(...)`; 1-50 chars after trim
    -> `InvalidAgentVersionError`
  - `description` wrapped via `AgentDescription(...)` when not None;
    1-2000 chars after trim -> `InvalidAgentDescriptionError`. None
    is allowed (means no description).
  - `canonical_uri` wrapped via `AgentCanonicalUri(...)` when not
    None; https-only + 1-2000 chars -> `InvalidAgentCanonicalUriError`.
    None is allowed.
  - Each `capability` wrapped via `AgentCapability(...)`; 1-100
    chars per entry -> `InvalidAgentCapabilityError`. Cardinality
    cap 32 -> `InvalidAgentCapabilitiesError`. Empty frozenset is
    allowed.
  - `model_ref` is a typed VO; its construction has already
    validated provider / model / snapshot_pin shape.

Initial status is implicit `Defined` (event type IS the state-change
indicator; the genesis evolver hardcodes the mapping).
"""

from datetime import datetime
from uuid import UUID

from cora.agent.aggregates.agent import (
    AGENT_CAPABILITIES_MAX_COUNT,
    Agent,
    AgentAlreadyExistsError,
    AgentCanonicalUri,
    AgentCapability,
    AgentDefined,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentVersion,
    InvalidAgentCapabilitiesError,
)
from cora.agent.features.define_agent.command import DefineAgent


def decide(
    state: Agent | None,
    command: DefineAgent,
    *,
    now: datetime,
    new_id: UUID,
) -> list[AgentDefined]:
    """Decide the events produced by defining a new Agent.

    Invariants:
      - State must be None (genesis-only) -> AgentAlreadyExistsError
      - Kind must be valid -> InvalidAgentKindError (via AgentKind VO)
      - Name must be valid -> InvalidAgentNameError (via AgentName VO)
      - Version must be valid -> InvalidAgentVersionError
        (via AgentVersion VO)
      - Description (when set) must be valid
        -> InvalidAgentDescriptionError (via AgentDescription VO)
      - Canonical URI (when set) must be https + within length bound
        -> InvalidAgentCanonicalUriError (via AgentCanonicalUri VO)
      - Capabilities count must not exceed AGENT_CAPABILITIES_MAX_COUNT
        -> InvalidAgentCapabilitiesError
      - Each capability must be valid -> InvalidAgentCapabilityError
        (via AgentCapability VO)
    """
    if state is not None:
        raise AgentAlreadyExistsError(state.id)

    # Validate + trim core fields via VOs (each raises Invalid<X> on bad input).
    kind = AgentKind(command.kind)
    name = AgentName(command.name)
    version = AgentVersion(command.version)

    description: AgentDescription | None = None
    if command.description is not None:
        description = AgentDescription(command.description)

    canonical_uri: AgentCanonicalUri | None = None
    if command.canonical_uri is not None:
        canonical_uri = AgentCanonicalUri(command.canonical_uri)

    # Validate capability cardinality + per-entry shape.
    if len(command.capabilities) > AGENT_CAPABILITIES_MAX_COUNT:
        raise InvalidAgentCapabilitiesError(len(command.capabilities))
    capabilities = frozenset(AgentCapability(c) for c in command.capabilities)

    return [
        AgentDefined(
            agent_id=new_id,
            kind=kind.value,
            name=name.value,
            version=version.value,
            model_ref=command.model_ref,
            description=description.value if description is not None else None,
            canonical_uri=canonical_uri.value if canonical_uri is not None else None,
            prompt_template_id=command.prompt_template_id,
            capabilities=frozenset(c.value for c in capabilities),
            occurred_at=now,
            # Recorded exactly as the caller named it, including None. The
            # evolver derives the effective brain when folding, so a stream
            # stays a faithful record of what was asked rather than of what
            # was inferred.
            brain=command.brain,
        )
    ]
