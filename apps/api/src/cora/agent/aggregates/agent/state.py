"""Agent aggregate state, value objects, FSM, and domain errors.

`Agent` is the config-only aggregate for the Agent BC. It carries
everything needed to identify an agent and pin its behavior for
reproducibility, but NO runtime, NO LLM invocation, NO Decision
integration (those land separately per [[project_run_debrief_design]]).

Per [[project_agent_bc_design]] the 3-state FSM is locked day one:

  Defined  -> Versioned    (via `version_agent`; ready-for-invocation)
  Defined  -> Deprecated   (via `deprecate_agent`; terminal)
  Versioned -> Deprecated  (via `deprecate_agent`; terminal)

Verb is `define` (matching Family / Zone / Conduit / Policy
template-aggregate convention), NOT `register` (Actor / Subject /
Asset instance-shape verb). FSM matches Method / Plan / Practice /
Family (`Defined -> Versioned -> Deprecated`). The research-memo
suggestion `Registered -> Published -> Retired` was rejected at
design lock for CORA-vocabulary-alignment and Actor-collision risk.

## VOs (bounded-text pattern reused)

`AgentKind` (1-100 chars), `AgentName` (1-100 chars), `AgentDescription`
(1-2000 chars), `AgentVersion` (1-50 chars), `AgentCanonicalUri` (1-2000
chars, must start with https://), `AgentCapability` (1-100 chars per
entry, cardinality cap 32).
All follow the `validate_bounded_text` + `object.__setattr__` pattern
from the shared `cora.shared.bounded_text` helper.

`ModelRef` is a 3-field VO (`provider` + `model` + optional
`snapshot_pin`); required at definition so the runtime LLM has the
model identity available immediately.

## Cross-BC identity sharing

`Agent.id` is the SAME UUID as Access BC's `Actor.id` for the same
agent. The `define_agent` slice writes both events atomically via
`EventStore.append_streams`. `Decision.actor_id` reference checks
work uniformly regardless of whether the actor is human or agent;
no polymorphism, no saga compensation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import assert_never
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.deprecation import DeprecationReason
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

AGENT_KIND_MAX_LENGTH = 100
AGENT_NAME_MAX_LENGTH = 100
AGENT_DESCRIPTION_MAX_LENGTH = 2000
AGENT_VERSION_MAX_LENGTH = 50
AGENT_CANONICAL_URI_MAX_LENGTH = 2000
AGENT_CAPABILITY_MAX_LENGTH = 100
AGENT_CAPABILITIES_MAX_COUNT = 32
AGENT_TOOL_NAME_MAX_LENGTH = 100
AGENT_TOOLS_MAX_COUNT = 32
MODEL_REF_PROVIDER_MAX_LENGTH = 100
MODEL_REF_MODEL_MAX_LENGTH = 200
BRAIN_RULE_MAX_LENGTH = 200
"""Bound on a Rule brain's name. Matched to `MODEL_REF_MODEL_MAX_LENGTH`
because the two are the same thing at different kinds: the identity of the
brain an Agent thinks with. Unbounded was tolerable while only seeds wrote it;
it is wire-supplied now."""
MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH = 100


class AgentStatus(StrEnum):
    """The Agent's lifecycle state.

    Four values:

      - `Defined`    -- registered as config; NOT yet ready for
                        invocation (the LLM subscribers' lifecycle
                        gate fires on Versioned only).
      - `Versioned`  -- promoted to ready-for-invocation; rainbow-
                        deploy-style signal. Multiple Versioned
                        Agents may exist concurrently (different
                        `id`s sharing `kind`).
      - `Suspended`  -- non-terminal operator-pause from
                        `Versioned`. Returns to
                        `Versioned` via `resume_agent`. Config
                        changes (tools, budget) still permitted so
                        the operator can fix permissions while
                        paused. Cannot re-Version from Suspended
                        (resume is its own dedicated verb).
      - `Deprecated` -- terminal; cannot be re-Defined or re-
                        Versioned. Future invocations must pick a
                        non-Deprecated Agent of the same kind.
                        Reachable from `Defined`, `Versioned`, or
                        `Suspended`.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    SUSPENDED = "Suspended"
    DEPRECATED = "Deprecated"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by VO __post_init__ + deciders)
# ---------------------------------------------------------------------------


class InvalidAgentKindError(ValueError):
    """The supplied agent kind is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent kind must be 1-{AGENT_KIND_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAgentNameError(ValueError):
    """The supplied agent name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent name must be 1-{AGENT_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAgentDescriptionError(ValueError):
    """The supplied agent description is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent description must be 1-{AGENT_DESCRIPTION_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAgentVersionError(ValueError):
    """The supplied agent version is empty, whitespace-only, or too long.

    No semver parsing today: any 1-50 char trimmed string is accepted.
    Convention (not enforced) is semver-like (`v1`, `1.0.0`, `2026-05-16`).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent version must be 1-{AGENT_VERSION_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAgentCanonicalUriError(ValueError):
    """The supplied canonical_uri is empty, whitespace-only, too long, or not https.

    Per RFC 8707 audience shape + A2A AgentCard convention: must be a
    valid `https://` URI with no fragment, 1-2000 chars after trim.
    Loose validation today: scheme check + length check + no `#` in
    the string. Strict URI parsing deferred until A2A endpoint ships.
    """

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"Agent canonical_uri invalid: {reason} (got: {value!r})")
        self.value = value
        self.reason = reason


class InvalidAgentCapabilityError(ValueError):
    """A supplied capability entry is empty, whitespace-only, or too long.

    Cardinality cap is enforced separately by the decider.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent capability must be 1-{AGENT_CAPABILITY_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class BrainIsNotLanguageModelError(ValueError):
    """An LLM call was routed to an Agent that does not think with a model.

    Reachable only by pointing a designated-agent setting at an Agent whose
    brain is a rule, which is a deployment misconfiguration rather than an
    operator mistake at the wire. Loud rather than tolerated: the quiet
    alternative is serving a module-default model under that Agent's
    identity, which is the exact shape of the sentinel this type replaced.
    """

    def __init__(self, kind: str | None) -> None:
        super().__init__(
            f"Agent brain must be a {BrainKind.LANGUAGE_MODEL.value} to serve an LLM call "
            f"(got: {kind!r})"
        )
        self.kind = kind


class InvalidBrainRefError(ValueError):
    """A `BrainRef`'s payload does not match its own `kind`.

    Raised by the VO rather than by a decider: the type exists so that a brain
    cannot be named ambiguously, so a half-filled one must not be constructible
    anywhere, including in a test fixture or a seed.
    """


class InvalidAgentCapabilitiesError(ValueError):
    """The supplied capabilities frozenset has too many entries."""

    def __init__(self, count: int) -> None:
        super().__init__(
            f"Agent capabilities must have at most {AGENT_CAPABILITIES_MAX_COUNT} entries "
            f"(got: {count})"
        )
        self.count = count


class InvalidAgentSuspensionReasonError(ValueError):
    """The supplied suspension reason is empty, whitespace-only, or too long.

    Mirrors `InvalidAgentSuspensionReasonError` shape. Suspension
    reason carries operator-supplied free text (cost-overrun,
    output-spike, model-regression context) that operators reading
    the audit log later need.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent suspension reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidToolNameError(ValueError):
    """The supplied MCP tool name is empty, whitespace-only, or too long.

    Cap matches MCP tool-naming convention as of 2025-11-25 spec
    revision; tightening to a formal BNF is a watch item in
    [[project-agent-lifecycle-grants-design]].
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Tool name must be 1-{AGENT_TOOL_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAgentToolsError(ValueError):
    """A grant_tool_to_agent call would push `Agent.tools` past
    `AGENT_TOOLS_MAX_COUNT` entries. Mirrors
    `InvalidAgentCapabilitiesError` shape."""

    def __init__(self, count: int) -> None:
        super().__init__(
            f"Agent tools must have at most {AGENT_TOOLS_MAX_COUNT} entries (got: {count})"
        )
        self.count = count


class InvalidAgentBudgetError(ValueError):
    """The supplied AgentBudget violates an invariant: both fields
    None (use `Agent.budget = None` for clearing), OR a negative
    cap."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"AgentBudget invalid: {reason}")
        self.reason = reason


class InvalidModelRefError(ValueError):
    """The supplied ModelRef has empty / whitespace-only / over-cap fields."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"ModelRef invalid: {reason}")
        self.reason = reason


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class AgentBrainUnspecifiedError(ValueError):
    """A `define_agent` command named neither a brain nor a legacy model_ref.

    An Agent that names nothing to think with produces an `AgentDefined` the
    evolver refuses to fold, so this is caught at write time rather than
    discovered at replay. The wire rejects it first; reaching this means an
    in-process caller.
    """

    def __init__(self) -> None:
        super().__init__("Agent must name exactly one of brain or model_ref")


class AgentAlreadyExistsError(Exception):
    """Attempted to define an agent whose stream already has events.

    Per [[project_genesis_error_classes]] this class stays un-hoisted:
    per-BC isinstance routing in the BC's exception handler outweighs
    the ~80 LOC saved by hoisting to a generic `AggregateAlreadyExists`.
    """

    def __init__(self, agent_id: UUID) -> None:
        super().__init__(f"Agent {agent_id} already exists")
        self.agent_id = agent_id


class AgentNotFoundError(Exception):
    """Attempted an operation on an agent whose stream has no events."""

    def __init__(self, agent_id: UUID) -> None:
        super().__init__(f"Agent {agent_id} not found")
        self.agent_id = agent_id


class AgentCannotVersionError(Exception):
    """Attempted `version_agent` from a disqualifying status.

    Single-source guard: source set is `{Defined}` only. Cannot version
    an already-Versioned or Deprecated agent. Multi-version-per-kind
    is achieved by defining a new Agent with the same `kind` and a
    different `id`, not by re-versioning the same `id`.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot be versioned: currently in status "
            f"{current_status.value}, version_agent requires {AgentStatus.DEFINED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotDeprecateError(Exception):
    """Attempted `deprecate_agent` from a disqualifying status.

    Source set is `{Defined, Versioned, Suspended}`. Cannot re-
    deprecate an already-Deprecated agent (strict-not-idempotent).
    `Suspended` is in the source set so an operator who paused an
    agent can still retire it without resuming first.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate_agent requires {AgentStatus.DEFINED.value}, "
            f"{AgentStatus.VERSIONED.value}, or {AgentStatus.SUSPENDED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotSuspendError(Exception):
    """Attempted `suspend_agent` from a disqualifying status.

    Source set is `{Versioned}` only. `Defined` agents aren't yet
    invocable so suspension is meaningless; `Suspended` agents are
    already paused (strict-not-idempotent); `Deprecated` agents are
    terminal.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot be suspended: currently in status "
            f"{current_status.value}, suspend_agent requires {AgentStatus.VERSIONED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotResumeError(Exception):
    """Attempted `resume_agent` from a disqualifying status.

    Source set is `{Suspended}` only. Resume's contract is
    "return a paused agent to active"; any other current state
    means the operator is doing the wrong thing.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot be resumed: currently in status "
            f"{current_status.value}, resume_agent requires {AgentStatus.SUSPENDED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotGrantToolError(Exception):
    """Attempted `grant_tool_to_agent` against a `Deprecated` agent.

    Tool grants are allowed from `Defined`, `Versioned`, AND
    `Suspended` so operators can fix permissions while an agent is
    paused. `Deprecated` is the only blocking state (terminal, no
    config changes).
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot grant tools: currently in status "
            f"{current_status.value}; grants are blocked in {AgentStatus.DEPRECATED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotRevokeToolError(Exception):
    """Attempted `revoke_tool_from_agent` against a `Deprecated` agent.

    Same source-set rule as `AgentCannotGrantToolError`.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot revoke tools: currently in status "
            f"{current_status.value}; revocations are blocked in "
            f"{AgentStatus.DEPRECATED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotUpdateBudgetError(Exception):
    """Attempted `update_agent_budget` against a `Deprecated` agent.

    Same source-set rule as `AgentCannotGrantToolError`.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot update budget: currently in status "
            f"{current_status.value}; updates are blocked in "
            f"{AgentStatus.DEPRECATED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotUpdateTargetPlanError(Exception):
    """Attempted `update_agent_target_plan` against a `Deprecated` agent.

    Same source-set rule as `AgentCannotUpdateBudgetError`.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot set target plan: currently in status "
            f"{current_status.value}; updates are blocked in "
            f"{AgentStatus.DEPRECATED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentNotSeededError(Exception):
    """Cross-aggregate load failure: the operator-triggered slice
    expected an Agent record at the supplied id but found none.

    Today raised by the `debrief_run`-style slices when
    the RunDebriefer Agent's bootstrap seed didn't run (deployment
    misconfiguration: `seed_run_debriefer_agent` not invoked at app
    startup, or the Agent stream was manually purged).

    Mirrors `DeciderActorNotFoundError` / `ProducingRunNotFoundError`
    / `LinkedSubjectNotFoundError` precedents: cross-aggregate-load
    failure errors live at the aggregate's state.py module per the
    cross-BC gate-review convention.
    """

    def __init__(self, agent_id: UUID, agent_name: str) -> None:
        super().__init__(
            f"Agent {agent_name} ({agent_id}) is not seeded; ensure the "
            "appropriate bootstrap seed ran at app startup"
        )
        self.agent_id = agent_id
        self.agent_name = agent_name


class AgentKindMismatchError(Exception):
    """Cross-aggregate gate failure: the named Agent is the wrong kind
    for the slice that was asked to run it.

    Raised when an operator names an explicit agent on a slice that is
    specific to one kind, such as pointing `regenerate_run_debrief` at a
    CautionDrafter. Without this the Decision would be written in the
    RunDebrief context but attributed to an agent that never debriefs
    anything, and the record would carry an attribution no reader could
    make sense of.
    """

    def __init__(self, agent_id: UUID, expected_kind: str, actual_kind: str) -> None:
        super().__init__(
            f"Agent {agent_id} is kind {actual_kind!r}, but this command "
            f"requires kind {expected_kind!r}"
        )
        self.agent_id = agent_id
        self.expected_kind = expected_kind
        self.actual_kind = actual_kind


class AgentDeactivatedError(Exception):
    """Cross-aggregate state-gate failure: the Agent's co-registered
    Actor is `active=False`.

    Today raised by the `debrief_run`-style slices when
    an operator deactivated the agent's Actor via Access BC.
    Recovery is operator-side: reactivate the Actor before re-
    invoking the agent.

    Mirrors the subscriber's runtime gate (`cora.agent.subscribers.
    run_debriefer.RunDebrieferSubscriber.apply` line: `if not
    actor.active: return`).
    """

    def __init__(self, agent_id: UUID) -> None:
        super().__init__(
            f"Agent's Actor {agent_id} is deactivated; reactivate via Access BC before invoking"
        )
        self.agent_id = agent_id


class AgentSuspendedError(Exception):
    """Cross-aggregate state-gate failure: the Agent is `Suspended`.

    Raised by operator-triggered slices (the regenerate path) when the
    target agent is under the reversible operator pause: suspension
    means the agent takes no actions, LLM calls included, and driving
    it through an on-demand slice would defeat the pause. Recovery is
    operator-side: `resume_agent` first.

    Mirrors the subscribers' lifecycle gate (only a Versioned agent
    acts).
    """

    def __init__(self, agent_id: UUID) -> None:
        super().__init__(f"Agent {agent_id} is suspended; resume via resume_agent before invoking")
        self.agent_id = agent_id


class AgentNotVersionedError(Exception):
    """Cross-aggregate state-gate failure: the Agent is not `Versioned`.

    `Defined` means registered as config but not yet promoted for
    invocation, and `Deprecated` is terminal. Neither may act.

    This gate exists on the subscriber path and did not exist here, and
    the disagreement was not academic. Every Decision on the 2-BM pilot
    record came through the on-demand path, which served a `Defined`
    agent happily, while the subscribers refused the same agent and
    recorded nothing at all. Whichever answer is right, the two paths
    cannot give different ones about the same agent.

    `Suspended` raises `AgentSuspendedError` instead, because its remedy
    is a different verb (`resume_agent`, not `version_agent`) and
    collapsing them would send an operator to the wrong one.
    """

    def __init__(self, agent_id: UUID, status: AgentStatus) -> None:
        super().__init__(
            f"Agent {agent_id} is {status.value}, not {AgentStatus.VERSIONED.value}; "
            "promote it via version_agent before invoking"
        )
        self.agent_id = agent_id
        self.status = status


# ---------------------------------------------------------------------------
# Bounded-text value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentKind:
    """Free-form kind discriminator. Trimmed; 1-100 chars.

    Bare-str at MVP per Supply.kind / Procedure.kind precedent. Closed
    `AgentKind` StrEnum deferred until vocabulary stabilizes (90 days
    pilot + <10 distinct kinds; [[project_agent_bc_design]] watch
    item).

    First registered kind day-1 = `RunDebriefer`.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_KIND_MAX_LENGTH,
            error_class=InvalidAgentKindError,
        )
        object.__setattr__(self, "value", trimmed)


@bounded_name(max_length=AGENT_NAME_MAX_LENGTH, error_class=InvalidAgentNameError)
@dataclass(frozen=True)
class AgentName:
    """Human-readable display name. Trimmed; 1-100 chars.

    Mirrors A2A AgentCard.name + OTel `gen_ai.agent.name` per the
    12-field interop identity surface in [[project_agent_bc_research]].
    """

    value: str


@dataclass(frozen=True)
class AgentDescription:
    """Free-form description. Trimmed; 1-2000 chars.

    Mirrors A2A AgentCard.description + OTel `gen_ai.agent.description`.
    Optional at the aggregate level; required by the VO when present
    (callers pass `None` instead of an empty string).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_DESCRIPTION_MAX_LENGTH,
            error_class=InvalidAgentDescriptionError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentVersion:
    """Semver-like version identifier. Trimmed; 1-50 chars.

    No semver parsing at MVP: any 1-50 char string is accepted.
    Convention (not enforced) is semver-like (`v1`, `1.0.0`,
    `2026-05-16`). Mirrors A2A AgentCard.version + OTel
    `gen_ai.agent.version`.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_VERSION_MAX_LENGTH,
            error_class=InvalidAgentVersionError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentCanonicalUri:
    """Optional canonical https URI. Trimmed; 1-2000 chars; must start with `https://`.

    Mirrors RFC 8707 audience + RFC 9728 + PROV-O `@id` + OTel
    `gen_ai.agent.id` per the 12-field interop identity surface.
    Loose validation today (scheme + length + no fragment); strict
    URI parsing deferred until A2A endpoint ships.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidAgentCanonicalUriError(self.value, "empty or whitespace-only")
        if len(trimmed) > AGENT_CANONICAL_URI_MAX_LENGTH:
            raise InvalidAgentCanonicalUriError(
                self.value, f"exceeds {AGENT_CANONICAL_URI_MAX_LENGTH} chars after trim"
            )
        if not trimmed.startswith("https://"):
            raise InvalidAgentCanonicalUriError(self.value, "must start with `https://`")
        if "#" in trimmed:
            raise InvalidAgentCanonicalUriError(self.value, "must not contain a fragment (`#`)")
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentCapability:
    """One free-form capability claim. Trimmed; 1-100 chars per entry.

    The aggregate carries `frozenset[AgentCapability]`. Cardinality cap
    is enforced separately by the decider. Bare-str at MVP per the
    same StrEnum-graduation precedent as AgentKind.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_CAPABILITY_MAX_LENGTH,
            error_class=InvalidAgentCapabilityError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentSuspensionReason:
    """Operator-supplied reason at suspension time. Trimmed; 1-500 chars.

    Bounded operator text; carries cost-overrun /
    output-spike / model-regression context operators reading the
    audit log later need.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidAgentSuspensionReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@bounded_name(max_length=AGENT_TOOL_NAME_MAX_LENGTH, error_class=InvalidToolNameError)
@dataclass(frozen=True)
class ToolName:
    """One MCP tool name in the agent's declared tool set.

    DECLARATION-ONLY today: the set is recorded by `grant_tool_to_agent`
    / `revoke_tool_from_agent` and surfaced in reads, but is NOT
    consulted at invocation. Nothing gates on it: the MCP edge registers
    every tool globally and dispatches by principal (never by
    `Agent.tools`), and the agent subscribers do not build tool-bearing
    LLM requests. So "the agent is authorized to invoke X" is recorded
    intent, not an enforced control, and revoking a tool changes no
    runtime behavior. The future enforcement point is an agent runtime
    that offers tools to the model. See
    memory/project_authorization_envelope_design.md (dead switches /
    Tier-1 #3).

    Bounded text 1-100 chars (matches MCP tool-naming convention;
    tightening to a formal BNF is a watch item). The aggregate carries
    `frozenset[ToolName]`. Cardinality cap enforced separately by the
    `grant_tool_to_agent` decider.
    """

    value: str


@dataclass(frozen=True)
class AgentBudget:
    """Optional per-agent budget caps, enforced at the coarse post-hoc tier.

    Both `monthly_usd_cap` and `daily_token_cap` are independently
    nullable so the same VO covers "set both", "set one, clear the
    other", and "set new monthly while keeping daily" cases. At least
    one must be non-None at construction (the no-budget shape is
    `Agent.budget = None` directly).

    Enforcement: the coarse post-hoc gate (`cora.agent._budget_gate`,
    consumed by the LLM subscribers) sums recorded spend from the
    inference entries' `cost_usd` and refuses the next call once a cap
    is exhausted; per-call telemetry also lands on the
    `cora.agent.llm.cost.usd` histogram. The per-call pre-estimate tier
    ships too (`cora.agent.adapters.budget_spend_guard`, gating the
    autonomous steering brain), as does the Budget BC's per-beamline
    Allocation envelope layered above these per-agent caps. Only the
    leak-free reserve-post-void tier remains unbuilt (evaluated at
    [[project-reserve-post-void-stage0]]).

    Zero caps allowed and enforced as the recorded "no spend" intent:
    the gate treats a 0 cap as a hard stop (zero spent >= zero cap
    refuses every call). Negative caps rejected.
    """

    monthly_usd_cap: float | None
    daily_token_cap: int | None

    def __post_init__(self) -> None:
        if self.monthly_usd_cap is None and self.daily_token_cap is None:
            raise InvalidAgentBudgetError(
                "at least one of monthly_usd_cap or daily_token_cap must be set; "
                "use Agent.budget = None to clear"
            )
        if self.monthly_usd_cap is not None and self.monthly_usd_cap < 0:
            raise InvalidAgentBudgetError(
                f"monthly_usd_cap must be >= 0 (got: {self.monthly_usd_cap})"
            )
        if self.daily_token_cap is not None and self.daily_token_cap < 0:
            raise InvalidAgentBudgetError(
                f"daily_token_cap must be >= 0 (got: {self.daily_token_cap})"
            )


@dataclass(frozen=True)
class ModelRef:
    """Model identity: provider + model + optional snapshot pin.

    Deviation from Identifier VO: 3-tuple per project-agent-bc-design
    mirroring OTel gen_ai.system + model + snapshot_pin.

    Required at `define_agent` (NOT at version_agent) so 8f-b's
    LLM has the model identity available the moment the Agent
    exists. Different `model_ref` = different Agent (changing model
    requires defining a new Agent with a new `id`).

    Mirrors OTel `gen_ai.system` (provider) + `gen_ai.request.model`
    (model) per [[project_agent_bc_research]] 12-field surface.
    `snapshot_pin` enables reproducibility-by-construction (Anthropic
    snapshot string, OpenAI model fingerprint, etc.).

    All three fields are trimmed and bounded; whitespace-only
    `snapshot_pin` is rejected (callers pass `None` to omit).
    """

    provider: str
    model: str
    snapshot_pin: str | None = None

    def __post_init__(self) -> None:
        provider_trimmed = self.provider.strip()
        if not provider_trimmed:
            raise InvalidModelRefError("provider must be non-empty after trim")
        if len(provider_trimmed) > MODEL_REF_PROVIDER_MAX_LENGTH:
            raise InvalidModelRefError(
                f"provider exceeds {MODEL_REF_PROVIDER_MAX_LENGTH} chars after trim"
            )

        model_trimmed = self.model.strip()
        if not model_trimmed:
            raise InvalidModelRefError("model must be non-empty after trim")
        if len(model_trimmed) > MODEL_REF_MODEL_MAX_LENGTH:
            raise InvalidModelRefError(
                f"model exceeds {MODEL_REF_MODEL_MAX_LENGTH} chars after trim"
            )

        snapshot_pin_trimmed: str | None
        if self.snapshot_pin is None:
            snapshot_pin_trimmed = None
        else:
            snapshot_pin_trimmed = self.snapshot_pin.strip()
            if not snapshot_pin_trimmed:
                raise InvalidModelRefError(
                    "snapshot_pin must be non-empty after trim if provided; pass None to omit"
                )
            if len(snapshot_pin_trimmed) > MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH:
                raise InvalidModelRefError(
                    f"snapshot_pin exceeds {MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH} chars after trim"
                )

        object.__setattr__(self, "provider", provider_trimmed)
        object.__setattr__(self, "model", model_trimmed)
        object.__setattr__(self, "snapshot_pin", snapshot_pin_trimmed)


# ---------------------------------------------------------------------------
# Agent aggregate state
# ---------------------------------------------------------------------------


class BrainKind(StrEnum):
    """What KIND of thinking part an Agent runs on.

    An Agent is an identity plus authority plus a brain. The brain is the part
    that decides; the Agent is the part that acts, holds the caps and can be
    stood down. Until this enum existed the brain slot was `ModelRef`, which
    only describes an LLM, so an Agent whose brain is a deterministic rule had
    to declare a sentinel `ModelRef` that its own comment admitted was never
    used to build an LLM.

    `OPTIMIZER` is deliberately ABSENT. A search brain (a Gaussian process, a
    Sobol seeder) is a real brain kind, but it has no catalog to be approved
    against yet, and adding a member here that no gate checks would ship a
    silently ungated brain. Widening this enum forces the `assert_never` in the
    approval dispatch to fail type-checking, so the gate cannot be forgotten.
    See [[project-brain-modeling-design]].
    """

    LANGUAGE_MODEL = "LanguageModel"
    RULE = "Rule"


@dataclass(frozen=True)
class BrainRef:
    """Which specific brain an Agent thinks with, discriminated by kind.

    Exactly one of the per-kind payloads is set, matching `kind`. The
    invariant is enforced here rather than at each call site, because the
    whole point of the type is that a caller cannot name a brain ambiguously.

    `model_ref` is set iff kind is LANGUAGE_MODEL, and is gated at
    `define_agent` against the approved `LanguageModel` catalog.
    `rule` is set iff kind is RULE: a deterministic decision rule, named and
    versioned (`ExperimentSteerer:v1`), which needs no approval because it
    runs no external model and spends nothing.
    """

    kind: BrainKind
    model_ref: ModelRef | None = None
    rule: str | None = None

    def __post_init__(self) -> None:
        match self.kind:
            case BrainKind.LANGUAGE_MODEL:
                if self.model_ref is None or self.rule is not None:
                    raise InvalidBrainRefError(
                        "a LanguageModel brain carries model_ref and no rule"
                    )
            case BrainKind.RULE:
                if self.rule is None or self.model_ref is not None:
                    raise InvalidBrainRefError("a Rule brain carries rule and no model_ref")
                rule_trimmed = self.rule.strip()
                if not rule_trimmed:
                    raise InvalidBrainRefError("rule must be non-empty after trim")
                if len(rule_trimmed) > BRAIN_RULE_MAX_LENGTH:
                    raise InvalidBrainRefError(
                        f"rule exceeds {BRAIN_RULE_MAX_LENGTH} chars after trim"
                    )
            case _:  # pragma: no cover - exhaustive over a closed enum
                assert_never(self.kind)

    @staticmethod
    def for_model(model_ref: ModelRef) -> "BrainRef":
        """The LanguageModel-kind brain for `model_ref`.

        Also the back-compat path: a stream written before `brain` existed
        carries only `model_ref`, and folds to exactly this.
        """
        return BrainRef(kind=BrainKind.LANGUAGE_MODEL, model_ref=model_ref)

    @staticmethod
    def for_rule(rule: str) -> "BrainRef":
        """The Rule-kind brain named `rule` (convention: `<Name>:v<N>`)."""
        return BrainRef(kind=BrainKind.RULE, rule=rule)


DETERMINISTIC_BRAIN_PROVIDER = "deterministic"
_SENTINEL_MODEL_PREFIX = "agent:"


def brain_from_legacy_model_ref(model_ref: ModelRef) -> BrainRef:
    """Read the brain a pre-`BrainRef` stream MEANT, from its `model_ref`.

    Eighteen seeded agents predate this type. `model_ref` was required and
    LLM-shaped, so the deterministic ones had to name a model they never call,
    and every one of them used the same deliberate sentinel: provider
    `deterministic`, model `agent:<Name>:v1`. That is a Rule brain written the
    only way the schema then allowed, and folding it to a LanguageModel brain
    would claim those agents think with a language model that does not exist
    and was never approved.

    Used ONLY when interpreting history, never when accepting new input. A
    caller defining an agent today states its brain explicitly; deriving Rule
    from a magic provider string at define time would let a caller skip the
    model-approval gate by naming a provider, which is a bypass rather than a
    reading. See the dispatch in `define_agent`'s handler.
    """
    if model_ref.provider == DETERMINISTIC_BRAIN_PROVIDER and model_ref.model.startswith(
        _SENTINEL_MODEL_PREFIX
    ):
        return BrainRef.for_rule(model_ref.model.removeprefix(_SENTINEL_MODEL_PREFIX))
    return BrainRef.for_model(model_ref)


@dataclass(frozen=True)
class Agent:
    """Aggregate root: an AI agent's typed configuration record.

    Config-only at genesis: no runtime, no LLM invocation, no Decision
    integration. Identity is a stable opaque `id: UUID` SHARED with
    Access BC's `Actor.id` for the same agent.

    Required day-1 fields: `id`, `kind`, `name`, `version`, `status`
    (defaults to `Defined` at construction; evolver sets explicitly).
    `brain` is not declared required by the type, but the evolver never
    produces state without one: see `_effective_brain` in the evolver.

    Optional fields: `description`, `canonical_uri`,
    `prompt_template_id` (None if no template registry entry exists;
    required by the RunDebriefer subscriber), `capabilities` (defaults
    to empty frozenset).

    Lifecycle additions: `tools` per-agent declared MCP tool set
    (recorded only; not consulted at invocation today, see `ToolName`);
    `budget` optional declarative caps (no enforcement at this
    layer); `suspended_at` / `resumed_at` / `suspension_reason`
    timestamps + reason for the `Suspended` non-terminal state.
    These STAY on aggregate state because `suspension_reason` is
    invariant-bearing — deciders read it.

    Lifecycle timestamps moved off state (Path C):
    `defined_at` / `versioned_at` / `deprecated_at` no longer live
    here. The projection (`proj_agent_summary`) folds those from
    event-payload `occurred_at`; readers compose them onto the
    response via `load_agent_timestamps`. Mirrors Method / Plan /
    Practice / Family / Capability. Suspended/Resumed timestamps
    stay because they pair with the invariant-bearing
    suspension_reason field.

    Forward-compat fold: legacy `AgentDefined` events from before
    lifecycle widening have no `tools` / `budget` keys; `from_stored`
    reads them via `payload.get(...)` returning `frozenset()` / `None`.
    Mirrors the `external_refs` + `campaign_id` additive precedents.

    Deferred fields (per design lock):
      - `provider_org` (A2A trigger)
      - `acts_on_behalf_of` (per-operator-agent trigger)
      - `card_signature` (A2A JWS trigger)
    """

    id: UUID
    kind: AgentKind
    name: AgentName
    version: AgentVersion
    # Legacy input path, written only by streams that predate `brain` and by
    # wire callers that still send it. None for anything defined since the
    # seeds moved over. Read `brain` instead; this field is kept so an old
    # stream stays a faithful record of what was written.
    model_ref: ModelRef | None = None
    # The brain, always present in folded state even for a stream written
    # before `brain` existed: the evolver derives one from `model_ref` in that
    # case, so a reader never has to know which era the stream came from.
    brain: BrainRef | None = None
    description: AgentDescription | None = None
    canonical_uri: AgentCanonicalUri | None = None
    prompt_template_id: UUID | None = None
    capabilities: frozenset[AgentCapability] = field(default_factory=frozenset[AgentCapability])
    status: AgentStatus = AgentStatus.DEFINED
    deprecation_reason: DeprecationReason | None = None
    # ToolGrant + Suspended + AgentBudget
    tools: frozenset[ToolName] = field(default_factory=frozenset[ToolName])
    budget: AgentBudget | None = None
    suspended_at: datetime | None = None
    resumed_at: datetime | None = None
    suspension_reason: AgentSuspensionReason | None = None
    # Fold-symmetry attribution halves paired with the suspended_at /
    # resumed_at lifecycle stamps per [[project_fold_symmetry_design]].
    # `suspended_by` is folded from `AgentSuspended.suspended_by` (the
    # principal that issued the suspend_agent command); `resumed_by`
    # from `AgentResumed.resumed_by`. Default-None so the additive-
    # state pattern keeps legacy reconstruction paths clean.
    suspended_by: ActorId | None = None
    resumed_by: ActorId | None = None
    # Runtime-mutable target Plan for an autonomous agent (the recipe the
    # RunInitiator starts for each ready Subject), set by `update_agent_target_plan`
    # and folded from `AgentTargetPlanUpdated`. Optional (None = unset); only the
    # consuming agent (RunInitiator) reads it, so it stays None for every other
    # agent kind. Additive-state default keeps legacy reconstruction clean.
    target_plan_id: UUID | None = None
