"""Domain events emitted by the Agent aggregate, plus the discriminated union.

Three genesis-and-lifecycle events:

  - `AgentDefined`    -- genesis (Defined). Written to a NEW Agent
                         stream by the `define_agent` slice ATOMICALLY
                         with `ActorRegistered(kind="agent")` on the
                         Access stream via `EventStore.append_streams`.
  - `AgentVersioned`  -- transition (Defined -> Versioned). Single
                         stream.
  - `AgentDeprecated` -- transition (Defined | Versioned -> Deprecated).
                         Single stream; terminal.

`model_ref` travels in the genesis payload as a JSON-friendly dict
with `{provider, model, snapshot_pin}`. The aggregate carries the
typed `ModelRef` VO; `to_payload` and the evolver bridge typed <->
wire via primitives.

`capabilities` travels in the genesis payload as a sorted `list[str]`
(deterministic bytes for idempotency replay), reconstructed into
`frozenset[AgentCapability]` by the evolver.

`prompt_template_id` and `canonical_uri` are `UUID | None` /
`str | None` in the payload; nullable fields use `payload.get(...)`
on the read path for forward-compat.

The deprecation reason on `AgentDeprecated` is a closed bounded-text
value (not an enum); travels as `str | None` in the payload.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.agent.aggregates.agent.state import ModelRef
from cora.infrastructure.event_payload import deserialize_or_raise, deserialize_vo_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

# ---------------------------------------------------------------------------
# ModelRef serialize / deserialize (public cross-slice helpers)
# ---------------------------------------------------------------------------


def serialize_model_ref(model_ref: ModelRef) -> dict[str, Any]:
    """Encode a typed ModelRef to a JSON-friendly dict.

    ModelRef(provider="anthropic", model="claude-sonnet-4-6",
             snapshot_pin="20251001")
      -> {"provider": "anthropic", "model": "claude-sonnet-4-6",
          "snapshot_pin": "20251001"}

    ModelRef(provider="openai", model="o4-mini", snapshot_pin=None)
      -> {"provider": "openai", "model": "o4-mini", "snapshot_pin": null}
    """
    return {
        "provider": model_ref.provider,
        "model": model_ref.model,
        "snapshot_pin": model_ref.snapshot_pin,
    }


def deserialize_model_ref(payload: dict[str, Any]) -> ModelRef:
    """Decode a JSON-friendly dict to a typed ModelRef.

    Raises ValueError on any field violation so a contaminated event
    payload fails loud at replay time.
    """
    return deserialize_vo_or_raise(
        "ModelRef",
        lambda: ModelRef(
            provider=payload["provider"],
            model=payload["model"],
            snapshot_pin=payload.get("snapshot_pin"),
        ),
    )


# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentDefined:
    """A new Agent was defined (genesis -> Defined).

    Co-written ATOMICALLY with Access BC's
    `ActorRegistered(kind="agent")` via `EventStore.append_streams`.
    The shared `agent_id` is the same UUID as the co-written Actor's
    `actor_id` (cross-BC identity sharing per
    [[project_agent_bc_design]]).

    Initial status implicitly `Defined` (event type IS the state-change
    indicator).
    """

    agent_id: UUID
    kind: str
    name: str
    version: str
    model_ref: ModelRef
    description: str | None
    canonical_uri: str | None
    prompt_template_id: UUID | None
    capabilities: frozenset[str]
    occurred_at: datetime
    # additive payload fields (default to
    # empty / None for backward-compat with 8f-a / 8f-b streams).
    tools: frozenset[str] = frozenset()
    monthly_usd_cap: float | None = None
    daily_token_cap: int | None = None


@dataclass(frozen=True)
class AgentVersioned:
    """A Defined Agent was promoted to Versioned (ready-for-invocation).

    Single-stream transition. The `version` value is carried for audit
    (matches the Agent's current `version` field at the time of
    promotion).
    """

    agent_id: UUID
    version: str
    occurred_at: datetime


@dataclass(frozen=True)
class AgentDeprecated:
    """An Agent was deprecated (terminal).

    Source set is `{Defined, Versioned, Suspended}` — operators
    can retire a paused agent without resuming first. `reason` is
    an optional operator-supplied bounded-text value (1-500 chars).

    The deprecating actor's id lives on the envelope
    (`StoredEvent.principal_id`); no actor field on the payload.
    """

    agent_id: UUID
    reason: str | None
    occurred_at: datetime


# ---------------------------------------------------------------------------
# events: Suspended FSM expansion + ToolGrant + Budget
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentSuspended:
    """A `Versioned` Agent was paused by operator command.

    Non-terminal: returns to `Versioned` via `resume_agent`. The
    `reason` field is REQUIRED (unlike `AgentDeprecated.reason`)
    because operator-pause is a high-information signal that the
    audit log should always carry context for.

    Fold-symmetry pair: `suspended_by` carries the suspending actor's
    id alongside `occurred_at`. Both halves fold onto the Agent
    aggregate state (`suspended_at` + `suspended_by`) per
    [[project_fold_symmetry_design]]. REVERSES the previous
    envelope-only convention for this event; the envelope still
    carries `principal_id` for cross-cutting audit, but the payload
    redundantly captures the same value under the canonical
    `<verb>_by` name so on-state reads answer attribution without
    crossing to the envelope.
    """

    agent_id: UUID
    reason: str
    suspended_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class AgentResumed:
    """A `Suspended` Agent was returned to `Versioned`.

    NO `reason` field by design: the act of resuming is its own
    signal; if rationale matters operators record a Decision
    separately. Asymmetry with `AgentSuspended.reason` is
    deliberate (events carry facts; Decisions carry rationale).

    Fold-symmetry pair: `resumed_by` carries the resuming actor's
    id alongside `occurred_at`. Both halves fold onto the Agent
    aggregate state (`resumed_at` + `resumed_by`) per
    [[project_fold_symmetry_design]]. REVERSES the previous
    envelope-only convention for this event.
    """

    agent_id: UUID
    resumed_by: ActorId
    occurred_at: datetime


@dataclass(frozen=True)
class AgentToolGranted:
    """One MCP tool was granted to an Agent.

    Idempotent: re-granting an already-granted tool emits NO event
    (the decider returns `[]`). The audit trail is the existing
    event log + the projected `Agent.tools` set.

    The granting actor's id lives on the envelope; no actor field
    on the payload.
    """

    agent_id: UUID
    tool_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class AgentToolRevoked:
    """One MCP tool was revoked from an Agent.

    Idempotent: re-revoking an already-revoked tool emits NO event.
    """

    agent_id: UUID
    tool_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class AgentBudgetUpdated:
    """The Agent's declarative budget caps were updated.

    Both `monthly_usd_cap` and `daily_token_cap` are nullable so
    the same event carries "set both", "set one, clear the other",
    and "clear all" cases. When both fields are None the Agent's
    `budget` field is set to None (no budget).

    Declaration only at this layer; enforcement deferred
    to 8h Budget BC adoption.
    """

    agent_id: UUID
    monthly_usd_cap: float | None
    daily_token_cap: int | None
    occurred_at: datetime


# Discriminated union of every event the Agent aggregate emits.
AgentEvent = (
    AgentDefined
    | AgentVersioned
    | AgentDeprecated
    | AgentSuspended
    | AgentResumed
    | AgentToolGranted
    | AgentToolRevoked
    | AgentBudgetUpdated
)


def event_type_name(event: AgentEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AgentEvent) -> dict[str, Any]:
    """Serialise an Agent event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, the typed `ModelRef` becomes a sub-dict via
    `serialize_model_ref`, and `capabilities` becomes a sorted list
    (deterministic bytes for byte-for-byte idempotency replay).
    """
    match event:
        case AgentDefined(
            agent_id=agent_id,
            kind=kind,
            name=name,
            version=version,
            model_ref=model_ref,
            description=description,
            canonical_uri=canonical_uri,
            prompt_template_id=prompt_template_id,
            capabilities=capabilities,
            occurred_at=occurred_at,
            tools=tools,
            monthly_usd_cap=monthly_usd_cap,
            daily_token_cap=daily_token_cap,
        ):
            return {
                "agent_id": str(agent_id),
                "kind": kind,
                "name": name,
                "version": version,
                "model_ref": serialize_model_ref(model_ref),
                "description": description,
                "canonical_uri": canonical_uri,
                "prompt_template_id": (
                    str(prompt_template_id) if prompt_template_id is not None else None
                ),
                "capabilities": sorted(capabilities),
                "occurred_at": occurred_at.isoformat(),
                # additive payload fields. Always
                # written so the wire shape is uniform; from_stored
                # falls back to defaults on pre-iter-2 streams.
                "tools": sorted(tools),
                "monthly_usd_cap": monthly_usd_cap,
                "daily_token_cap": daily_token_cap,
            }
        case AgentVersioned(agent_id=agent_id, version=version, occurred_at=occurred_at):
            return {
                "agent_id": str(agent_id),
                "version": version,
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentDeprecated(agent_id=agent_id, reason=reason, occurred_at=occurred_at):
            return {
                "agent_id": str(agent_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentSuspended(
            agent_id=agent_id,
            reason=reason,
            suspended_by=suspended_by,
            occurred_at=occurred_at,
        ):
            return {
                "agent_id": str(agent_id),
                "reason": reason,
                "suspended_by": str(suspended_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentResumed(agent_id=agent_id, resumed_by=resumed_by, occurred_at=occurred_at):
            return {
                "agent_id": str(agent_id),
                "resumed_by": str(resumed_by),
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentToolGranted(agent_id=agent_id, tool_name=tool_name, occurred_at=occurred_at):
            return {
                "agent_id": str(agent_id),
                "tool_name": tool_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentToolRevoked(agent_id=agent_id, tool_name=tool_name, occurred_at=occurred_at):
            return {
                "agent_id": str(agent_id),
                "tool_name": tool_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentBudgetUpdated(
            agent_id=agent_id,
            monthly_usd_cap=monthly_usd_cap,
            daily_token_cap=daily_token_cap,
            occurred_at=occurred_at,
        ):
            return {
                "agent_id": str(agent_id),
                "monthly_usd_cap": monthly_usd_cap,
                "daily_token_cap": daily_token_cap,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> AgentEvent:
    """Rebuild an Agent event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    Nullable fields (`description`, `canonical_uri`,
    `prompt_template_id`, `reason`) use `payload.get(...)` for
    forward-compat.
    """
    payload = stored.payload
    match stored.event_type:
        case "AgentDefined":

            def _build_agent_defined() -> AgentDefined:
                prompt_template_id_raw = payload.get("prompt_template_id")
                return AgentDefined(
                    agent_id=UUID(payload["agent_id"]),
                    kind=payload["kind"],
                    name=payload["name"],
                    version=payload["version"],
                    model_ref=deserialize_model_ref(payload["model_ref"]),
                    description=payload.get("description"),
                    canonical_uri=payload.get("canonical_uri"),
                    prompt_template_id=(
                        UUID(prompt_template_id_raw) if prompt_template_id_raw is not None else None
                    ),
                    capabilities=frozenset(payload.get("capabilities", [])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    tools=frozenset(payload.get("tools", [])),
                    monthly_usd_cap=payload.get("monthly_usd_cap"),
                    daily_token_cap=payload.get("daily_token_cap"),
                )

            return deserialize_or_raise("AgentDefined", _build_agent_defined)
        case "AgentVersioned":
            return deserialize_or_raise(
                "AgentVersioned",
                lambda: AgentVersioned(
                    agent_id=UUID(payload["agent_id"]),
                    version=payload["version"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AgentDeprecated":
            return deserialize_or_raise(
                "AgentDeprecated",
                lambda: AgentDeprecated(
                    agent_id=UUID(payload["agent_id"]),
                    reason=payload.get("reason"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AgentSuspended":
            return deserialize_or_raise(
                "AgentSuspended",
                lambda: AgentSuspended(
                    agent_id=UUID(payload["agent_id"]),
                    reason=payload["reason"],
                    suspended_by=ActorId(UUID(payload["suspended_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AgentResumed":
            return deserialize_or_raise(
                "AgentResumed",
                lambda: AgentResumed(
                    agent_id=UUID(payload["agent_id"]),
                    resumed_by=ActorId(UUID(payload["resumed_by"])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AgentToolGranted":
            return deserialize_or_raise(
                "AgentToolGranted",
                lambda: AgentToolGranted(
                    agent_id=UUID(payload["agent_id"]),
                    tool_name=payload["tool_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AgentToolRevoked":
            return deserialize_or_raise(
                "AgentToolRevoked",
                lambda: AgentToolRevoked(
                    agent_id=UUID(payload["agent_id"]),
                    tool_name=payload["tool_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AgentBudgetUpdated":
            return deserialize_or_raise(
                "AgentBudgetUpdated",
                lambda: AgentBudgetUpdated(
                    agent_id=UUID(payload["agent_id"]),
                    monthly_usd_cap=payload.get("monthly_usd_cap"),
                    daily_token_cap=payload.get("daily_token_cap"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown AgentEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AgentBudgetUpdated",
    "AgentDefined",
    "AgentDeprecated",
    "AgentEvent",
    "AgentResumed",
    "AgentSuspended",
    "AgentToolGranted",
    "AgentToolRevoked",
    "AgentVersioned",
    "deserialize_model_ref",
    "event_type_name",
    "from_stored",
    "serialize_model_ref",
    "to_payload",
]
