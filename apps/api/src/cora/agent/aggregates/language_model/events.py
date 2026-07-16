"""Domain events emitted by the LanguageModel aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`, plus the
cost-basis serialize / deserialize helpers.

Five genesis-and-lifecycle events:

  - `LanguageModelDefined`             -- genesis (Defined)
  - `LanguageModelApproved`            -- transition (Defined -> Approved)
  - `LanguageModelRetirementAnnounced` -- transition (Approved ->
                                          RetirementAnnounced); the VENDOR's
                                          lifecycle fact
  - `LanguageModelRetired`             -- transition (Approved |
                                          RetirementAnnounced -> Retired);
                                          terminal
  - `LanguageModelDeprecated`          -- transition (Defined | Approved |
                                          RetirementAnnounced -> Deprecated);
                                          terminal, the FACILITY's withdrawal

Events carry primitives (str / float / dict), not the state VOs,
matching how `AgentDefined` carries plain strings: the evolver wraps
primitives back into VOs at fold time, so payload bytes stay decoupled
from VO validation churn.

`cost_basis` travels in the genesis payload as a JSON-friendly dict
with a `"kind"` discriminator (`TokenPricing` or `GpuHourPricing`)
plus the variant's rate fields. The aggregate carries the typed
`CostBasis` union; the serialize / deserialize helpers bridge
typed <-> wire.

`model_ref` travels flattened into the genesis payload as `provider`
/ `model` / `snapshot_pin` primitives (the Agent aggregate's ModelRef
sub-dict shape is not reused because this event carries no nested VO
at all).

The acting principal's id lives ONLY on the envelope
(`StoredEvent.principal_id`); no actor field on any payload.

## Public `cost_basis_to_payload` / `cost_basis_from_payload` helpers

No leading underscore: sanctioned cross-slice helpers consumed by
both the `define_language_model` decider (to build the payload dict
from the typed CostBasis) and the evolver (to rebuild the typed
CostBasis from the payload). Same convention as Caution's
`serialize_target` / `deserialize_target`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.agent.aggregates.language_model.state import (
    CostBasis,
    GpuHourPricing,
    TokenPricing,
)
from cora.infrastructure.event_payload import deserialize_or_raise, deserialize_vo_or_raise
from cora.infrastructure.ports.event_store import StoredEvent

# ---------------------------------------------------------------------------
# CostBasis serialize / deserialize (public cross-slice helpers)
# ---------------------------------------------------------------------------


def cost_basis_to_payload(cost_basis: CostBasis) -> dict[str, Any]:
    """Encode a typed CostBasis to a JSON-friendly dict.

    The dict carries a `"kind"` discriminator plus the variant's rate
    fields:

      TokenPricing(...)   -> {"kind": "TokenPricing", "input_per_mtok": ...,
                              "output_per_mtok": ..., "cache_write_per_mtok": ...,
                              "cache_read_per_mtok": ...}
      GpuHourPricing(...) -> {"kind": "GpuHourPricing", "usd_per_gpu_hour": ...}
    """
    match cost_basis:
        case TokenPricing(
            input_per_mtok=input_per_mtok,
            output_per_mtok=output_per_mtok,
            cache_write_per_mtok=cache_write_per_mtok,
            cache_read_per_mtok=cache_read_per_mtok,
        ):
            return {
                "kind": "TokenPricing",
                "input_per_mtok": input_per_mtok,
                "output_per_mtok": output_per_mtok,
                "cache_write_per_mtok": cache_write_per_mtok,
                "cache_read_per_mtok": cache_read_per_mtok,
            }
        case GpuHourPricing(usd_per_gpu_hour=usd_per_gpu_hour):
            return {
                "kind": "GpuHourPricing",
                "usd_per_gpu_hour": usd_per_gpu_hour,
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(cost_basis)


def cost_basis_from_payload(payload: dict[str, Any]) -> CostBasis:
    """Decode a JSON-friendly dict to a typed CostBasis.

    Dispatches on `payload["kind"]`; an unknown discriminator raises
    ValueError inside the builder so the wrap re-raises it as
    `Malformed CostBasis payload` (a contaminated event payload fails
    loud at fold time rather than silently coercing).
    `extra=(ValueError,)` also folds the VO constructors' own
    `InvalidCostBasisError` (negative or non-finite rate) into the
    same Malformed wrap.
    """

    def _build() -> CostBasis:
        kind = payload["kind"]
        match kind:
            case "TokenPricing":
                return TokenPricing(
                    input_per_mtok=payload["input_per_mtok"],
                    output_per_mtok=payload["output_per_mtok"],
                    cache_write_per_mtok=payload["cache_write_per_mtok"],
                    cache_read_per_mtok=payload["cache_read_per_mtok"],
                )
            case "GpuHourPricing":
                return GpuHourPricing(usd_per_gpu_hour=payload["usd_per_gpu_hour"])
            case _:
                msg = f"Unknown CostBasis kind: {kind!r}"
                raise ValueError(msg)

    return deserialize_vo_or_raise("CostBasis", _build, extra=(ValueError,))


# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LanguageModelDefined:
    """A new catalog entry was defined (genesis -> Defined).

    Initial status implicitly `Defined` (event type IS the state-change
    indicator; the genesis evolver hardcodes the mapping). A Defined
    entry is registered but NOT yet usable: the define_agent gate
    requires Approved. Approval is the governance act; the seed
    precedent for skipping it at bootstrap is Safety's
    clearance-template seed (Defined + Activated in one append), not
    the agent-fleet seeds (those land Defined and are gated at runtime
    by `Actor.active`, not `AgentStatus`).

    `served_via` / `data_tier` / `archivability` travel as the
    StrEnum string values; `cost_basis` as the discriminated dict.
    """

    language_model_id: UUID
    name: str
    provider: str
    model: str
    snapshot_pin: str | None
    served_via: str
    endpoint_note: str | None
    cost_basis: dict[str, Any]
    data_tier: str
    archivability: str
    occurred_at: datetime


@dataclass(frozen=True)
class LanguageModelApproved:
    """A Defined entry was approved (Defined -> Approved).

    The facility's governance act: from this moment the entry is
    usable for its declared data tier and the pricing bridge may feed
    from it. No reason field: approval rationale, when it matters,
    lives in a Decision, not on the fact.
    """

    language_model_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class LanguageModelRetirementAnnounced:
    """The vendor announced this model will cease to exist (Approved -> RetirementAnnounced).

    The paper's governance-event claim: the announcement becomes an
    appended fact the at-risk-results projection reads. `reason` is
    REQUIRED (the announcement always carries vendor context worth
    auditing); `effective_at` is the vendor's announced cutoff, None
    when the vendor gave a warning but no date.
    """

    language_model_id: UUID
    reason: str
    effective_at: datetime | None
    occurred_at: datetime


@dataclass(frozen=True)
class LanguageModelRetired:
    """The model is no longer servable (Approved | RetirementAnnounced -> Retired). Terminal.

    Reachable directly from Approved because providers remove models
    without notice; `reason` is optional for the same reason (an
    unannounced removal may arrive with no vendor statement at all,
    and a None here preserves any earlier announcement's reason on
    the folded state).
    """

    language_model_id: UUID
    reason: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class LanguageModelDeprecated:
    """The facility withdrew its approval (any pre-terminal status -> Deprecated). Terminal.

    Distinct from `LanguageModelRetired` because the two terminals
    answer different audit questions (who ended this model's service
    life, the vendor or us?). `reason` is REQUIRED: withdrawing
    approval is a policy act the audit log must always carry context
    for.
    """

    language_model_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the LanguageModel aggregate emits.
LanguageModelEvent = (
    LanguageModelDefined
    | LanguageModelApproved
    | LanguageModelRetirementAnnounced
    | LanguageModelRetired
    | LanguageModelDeprecated
)


def event_type_name(event: LanguageModelEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: LanguageModelEvent) -> dict[str, Any]:
    """Serialise a LanguageModel event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings; `cost_basis` is already the discriminated dict (fixed
    key set per kind, so payload bytes stay deterministic for
    byte-for-byte idempotency replay).
    """
    match event:
        case LanguageModelDefined(
            language_model_id=language_model_id,
            name=name,
            provider=provider,
            model=model,
            snapshot_pin=snapshot_pin,
            served_via=served_via,
            endpoint_note=endpoint_note,
            cost_basis=cost_basis,
            data_tier=data_tier,
            archivability=archivability,
            occurred_at=occurred_at,
        ):
            return {
                "language_model_id": str(language_model_id),
                "name": name,
                "provider": provider,
                "model": model,
                "snapshot_pin": snapshot_pin,
                "served_via": served_via,
                "endpoint_note": endpoint_note,
                "cost_basis": cost_basis,
                "data_tier": data_tier,
                "archivability": archivability,
                "occurred_at": occurred_at.isoformat(),
            }
        case LanguageModelApproved(
            language_model_id=language_model_id,
            occurred_at=occurred_at,
        ):
            return {
                "language_model_id": str(language_model_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case LanguageModelRetirementAnnounced(
            language_model_id=language_model_id,
            reason=reason,
            effective_at=effective_at,
            occurred_at=occurred_at,
        ):
            return {
                "language_model_id": str(language_model_id),
                "reason": reason,
                "effective_at": (effective_at.isoformat() if effective_at is not None else None),
                "occurred_at": occurred_at.isoformat(),
            }
        case LanguageModelRetired(
            language_model_id=language_model_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "language_model_id": str(language_model_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case LanguageModelDeprecated(
            language_model_id=language_model_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "language_model_id": str(language_model_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> LanguageModelEvent:
    """Rebuild a LanguageModel event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    Each arm delegates to `deserialize_or_raise`, which catches
    KeyError / TypeError / AttributeError and re-raises as ValueError
    tagged with the event-type name. `cost_basis` travels through as
    the raw dict; its discriminator is validated at fold time by
    `cost_basis_from_payload` (the event carries primitives, the
    evolver owns VO reconstruction).

    Nullable fields (`snapshot_pin`, `endpoint_note`, `effective_at`,
    the Retired arm's `reason`) use `payload.get(...)` so future
    migrations that add new nullable fields remain forward-compat at
    replay time.
    """
    payload = stored.payload
    match stored.event_type:
        case "LanguageModelDefined":

            def _build_defined() -> LanguageModelDefined:
                return LanguageModelDefined(
                    language_model_id=UUID(payload["language_model_id"]),
                    name=payload["name"],
                    provider=payload["provider"],
                    model=payload["model"],
                    snapshot_pin=payload.get("snapshot_pin"),
                    served_via=payload["served_via"],
                    endpoint_note=payload.get("endpoint_note"),
                    cost_basis=payload["cost_basis"],
                    data_tier=payload["data_tier"],
                    archivability=payload["archivability"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("LanguageModelDefined", _build_defined)
        case "LanguageModelApproved":
            return deserialize_or_raise(
                "LanguageModelApproved",
                lambda: LanguageModelApproved(
                    language_model_id=UUID(payload["language_model_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "LanguageModelRetirementAnnounced":

            def _build_retirement_announced() -> LanguageModelRetirementAnnounced:
                effective_at_raw = payload.get("effective_at")
                return LanguageModelRetirementAnnounced(
                    language_model_id=UUID(payload["language_model_id"]),
                    reason=payload["reason"],
                    effective_at=(
                        datetime.fromisoformat(effective_at_raw)
                        if effective_at_raw is not None
                        else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise(
                "LanguageModelRetirementAnnounced", _build_retirement_announced
            )
        case "LanguageModelRetired":
            return deserialize_or_raise(
                "LanguageModelRetired",
                lambda: LanguageModelRetired(
                    language_model_id=UUID(payload["language_model_id"]),
                    reason=payload.get("reason"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "LanguageModelDeprecated":
            return deserialize_or_raise(
                "LanguageModelDeprecated",
                lambda: LanguageModelDeprecated(
                    language_model_id=UUID(payload["language_model_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown LanguageModelEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "LanguageModelApproved",
    "LanguageModelDefined",
    "LanguageModelDeprecated",
    "LanguageModelEvent",
    "LanguageModelRetired",
    "LanguageModelRetirementAnnounced",
    "cost_basis_from_payload",
    "cost_basis_to_payload",
    "event_type_name",
    "from_stored",
    "to_payload",
]
