# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""CautionDrafter subscriber: CORA's second side-effecting subscriber.

Subscribes to the four terminal Run events (`RunCompleted`,
`RunAborted`, `RunStopped`, `RunTruncated`), loads the terminated
Run + Plan (for candidate Assets) + existing Active Cautions for
those Assets, asks the LLM for a structured
Caution-proposal Decision (`choice` + `confidence` + `confidence_band`
+ `reasoning` + optional `proposed_caution` tuple), and emits one
`DecisionRegistered` per terminal event with
`context = "CautionProposal"`.

## Sibling to RunDebrieferSubscriber

Subscribes to the SAME 4 terminal Run events as RunDebriefer. The
two subscribers run concurrently and INDEPENDENTLY in the
projection worker (per [[project-caution-drafter-design]] Q4 lock:
don't widen the subscriber framework). Each derives its
own Decision id from `(agent_kind, terminal_event_id)` so the two
streams never collide.

Named widening triggers (per design memo Locks > Subscriber
framework section): widen at 3rd side-effecting subscriber OR
per-event work exceeds 50ms OR first cross-subscriber ordering
dependency materializes. None of those hold today.

## V1 simplifications

  - Read scope = Run + Plan (for asset_ids) + existing Cautions
    via CautionLookup. Deferred: RunReading + ConduitTraversal +
    RunDebriefer's prior Decision (DecisionLookup port deferred to
    watch item #14 per design memo).
  - Defaults to `NoAction` aggressively (target 65-75% per Epic
    Sepsis lesson).
  - Tier quota (EEMUA 191 80/15/5) is telemetry-only, not enforced
    in code today.
  - Confidence band always emitted; no behavior-gating at v1.

## Decision shape

CautionDrafter writes `DecisionRegistered` with:
  - `context = "CautionProposal"`
  - `choice ∈ CAUTION_PROPOSAL_CHOICES`
  - `actor_id = CAUTION_DRAFTER_AGENT_ID`
  - `rule = "agent:CautionDrafter:v1"`
  - `confidence_source = "self_reported"`
  - `inputs` carries the proposed-Caution tuple + confidence_band
    + `informed_by_decision_id` (always None at v1; reserved for
    future DecisionLookup-driven cross-Decision linkage).

## NoAction fallback (parallel to RunDebriefer's DebriefDeferred)

On LLM exhaust, the subscriber writes a `choice="NoAction"`
Decision with `inputs={"reason": "LLM exhausted; deferred", ...}`
to preserve the exactly-one-Decision-per-terminal-Run audit
invariant. Operators see which Runs the agent couldn't draft a
proposal for and can re-trigger manually (future re-draft slice
deferred).

## Authorize + actor gate

Mirrors RunDebriefer verbatim: NO `Authorize` port call (agent's
authority granted at definition time); DOES gate on
`Actor.active` (operator-revocation gate per the security
gate-review convention).

## Cross-BC reads

  - `Run`  via `cora.run.aggregates.run.load_run`
  - `Plan` via `cora.recipe.aggregates.plan.load_plan` (for
    candidate Asset ids)
  - Existing Cautions via `kernel.caution_lookup`
    (shared port with the non-blocking banner)
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.prompts import (
    CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
    CandidateTarget,
    CautionDrafterPayload,
    ExistingCaution,
    build_caution_drafter_chat_request,
)
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    CAUTION_DRAFTER_AGENT_NAME,
)
from cora.agent.subscribers._terminal_run_helpers import (
    extract_interrupted_at,
    extract_reason,
)
from cora.agent.subscribers.run_debriefer import redact_secrets
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    event_type_name,
    to_payload,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError, LLMError
from cora.infrastructure.signing import SIGNED_EVENT_TYPES
from cora.recipe.aggregates.plan import load_plan
from cora.run.aggregates.run import load_run

if TYPE_CHECKING:
    from cora.access.aggregates.actor import Actor
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import LLM, CautionLookup, Signer
    from cora.infrastructure.ports.event_store import EventStore, NewEvent, StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "CautionDrafterSubscriber"
_DECISION_RULE = "agent:CautionDrafter:v1"

# Stable namespace for deriving deterministic Decision IDs from
# terminal Run event IDs. Distinct from RunDebriefer's namespace so
# both subscribers can fire on the same event without colliding on
# decision_id.
_CAUTION_DRAFTER_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000bbbb0002")

# Same 4 terminal Run events as RunDebriefer (per design memo Locks).
_TERMINAL_RUN_EVENTS = frozenset(
    {
        "RunCompleted",
        "RunAborted",
        "RunStopped",
        "RunTruncated",
    }
)

_log = get_logger(__name__)


def _derive_decision_id(terminal_event_id: UUID) -> UUID:
    """Deterministic Decision id from terminal event id (UUIDv5)."""
    return uuid5(_CAUTION_DRAFTER_DECISION_NAMESPACE, str(terminal_event_id))


# Extractors hoisted to `_terminal_run_helpers` (rule-of-three);
# imported above as `extract_reason` / `extract_interrupted_at`.


class CautionDrafterSubscriber:
    """Reaction: terminal Run -> one Caution-proposal Decision.

    Constructed by `make_caution_drafter_subscriber` from the Kernel;
    satisfies the `Reaction` Protocol structurally.

    Holds references to the LLM port, event store, and CautionLookup
    port. The Decision's `actor_id` is the seeded CautionDrafter
    Agent's id (== that agent's Actor.id per 8f-a's identity-sharing
    invariant).

    `batch_size = 1` for the same reason as RunDebriefer: the apply
    path includes a slow LLM round-trip, so holding the bookmark
    transaction across N events would starve Projection advance loops
    sharing the same pool.
    """

    name = "caution_drafter"
    subscribed_event_types = _TERMINAL_RUN_EVENTS
    batch_size = 1

    def __init__(
        self,
        *,
        event_store: EventStore,
        llm: LLM,
        caution_lookup: CautionLookup,
        signer: Signer | None = None,
    ) -> None:
        self.event_store = event_store
        self.llm = llm
        self.caution_lookup = caution_lookup
        self.signer = signer

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        """Process one terminal Run event."""
        _ = conn  # see RunDebrieferSubscriber.apply docstring; not used at v1
        if event.event_type not in _TERMINAL_RUN_EVENTS:
            return  # defensive; worker already filtered

        run_id = UUID(event.payload["run_id"])
        decision_id = _derive_decision_id(event.event_id)
        terminal_event_reason = extract_reason(event)
        interrupted_at = extract_interrupted_at(event)

        log = _log.bind(
            subscriber=self.name,
            command_name=_COMMAND_NAME,
            run_id=str(run_id),
            terminal_event_id=str(event.event_id),
            terminal_event_type=event.event_type,
            derived_decision_id=str(decision_id),
            correlation_id=str(event.correlation_id),
        )
        log.info("caution_drafter.start")

        # Load Run aggregate.
        run = await load_run(self.event_store, run_id)
        if run is None:
            log.warning("caution_drafter.skip.run_missing")
            return

        # Pre-load Plan for candidate Asset ids. The Plan's
        # `asset_ids` is the v1 candidate-target set; v1 does NOT
        # propose against Procedures (Procedure-targeting deferred
        # to v2 when Procedure-binding-on-Run lands).
        plan = await load_plan(self.event_store, run.plan_id)
        if plan is None:
            log.warning(
                "caution_drafter.skip.plan_missing",
                plan_id=str(run.plan_id),
            )
            return

        # Pre-load the Agent's Actor + revocation gate (mirrors
        # RunDebriefer verbatim).
        actor = await load_actor(self.event_store, CAUTION_DRAFTER_AGENT_ID)
        if actor is None:
            log.warning(
                "caution_drafter.skip.agent_actor_missing",
                agent_id=str(CAUTION_DRAFTER_AGENT_ID),
                agent_name=CAUTION_DRAFTER_AGENT_NAME,
            )
            return
        if not actor.active:
            log.warning(
                "caution_drafter.skip.agent_actor_deactivated",
                agent_id=str(CAUTION_DRAFTER_AGENT_ID),
                agent_name=CAUTION_DRAFTER_AGENT_NAME,
            )
            return

        # Build candidate-target list from Plan.asset_ids. v1 doesn't
        # include Procedures (Run aggregate doesn't yet carry a
        # procedure binding); per design memo, watch item for when
        # Procedure-on-Run binding ships.
        candidate_targets = tuple(
            CandidateTarget(
                target_kind="Asset",
                target_id=asset_id,
                target_name=f"Asset {asset_id}",  # name lookup deferred (would need cross-BC read)
            )
            for asset_id in sorted(plan.asset_ids)
        )

        # Look up existing Active Cautions for the candidate Assets.
        # CautionLookup's `find_active_for_run` is the load-bearing
        # shared port with the non-blocking banner; passing `min_severity="Notice"` so
        # CautionDrafter sees the full picture (banner uses default
        # min_severity="Caution"; this consumer wants everything).
        existing_caution_refs = await self.caution_lookup.find_active_for_run(
            asset_ids=plan.asset_ids,
            procedure_ids=frozenset(),
            min_severity="Notice",
        )
        existing_cautions = tuple(
            ExistingCaution(
                caution_id=cref.caution_id,
                category=cref.category,
                severity=cref.severity,
                text_excerpt=cref.text_excerpt,
                workaround_excerpt=cref.workaround_excerpt,
            )
            for cref in existing_caution_refs
        )

        payload = CautionDrafterPayload(
            terminal_event_type=event.event_type,
            terminal_event_reason=terminal_event_reason,
            terminal_event_occurred_at=event.occurred_at.isoformat(),
            run_id=run_id,
            run_name=run.name.value,
            run_status=str(run.status),
            plan_id=run.plan_id,
            subject_id=run.subject_id,
            campaign_id=run.campaign_id,
            effective_parameters=run.effective_parameters,
            adjustment_count=run.adjustment_count,
            last_adjusted_at=(
                run.last_adjusted_at.isoformat() if run.last_adjusted_at is not None else None
            ),
            interrupted_at=interrupted_at,
            candidate_targets=candidate_targets,
            existing_cautions=existing_cautions,
        )
        request = build_caution_drafter_chat_request(payload)

        try:
            response = await self.llm.chat(request)
        except LLMError as exc:
            log.warning(
                "caution_drafter.llm_failed",
                error_class=type(exc).__name__,
                error_message=redact_secrets(str(exc)[:200]),
            )
            await self._write_noaction_deferred(
                decision_id=decision_id,
                actor=actor,
                run_id=run_id,
                terminal_event=event,
                error_class=type(exc).__name__,
                log=log,
            )
            return

        await self._write_proposal(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=event,
            parsed=response.parsed,
            valid_target_ids=plan.asset_ids,
            log=log,
        )

    async def _write_proposal(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        parsed: Any,
        valid_target_ids: frozenset[UUID],
        log: Any,
    ) -> None:
        """Compose + append the LLM-success Decision.

        Parsed shape per CAUTION_DRAFTER_OUTPUT_SCHEMA:
          - choice: str (one of CAUTION_PROPOSAL_CHOICES)
          - confidence: float in [0, 1]
          - confidence_band: "low" | "medium" | "high"
          - reasoning: str
          - proposed_caution: dict (only when choice != "NoAction")

        `valid_target_ids` is the closed set of Asset UUIDs the prompt
        surfaced as `candidate_targets`. The schema constrains the LLM
        to return ONE of these, but a hallucinated/buggy LLM can emit
        an arbitrary UUID anyway; we defend by re-validating membership
        here and falling back to NoAction-deferred on miss (avoids
        landing a Decision against an unknown target that the operator
        would then have no Run-context to promote).
        """
        choice = str(parsed["choice"])
        confidence = float(parsed["confidence"])
        confidence_band = str(parsed["confidence_band"])
        reasoning = str(parsed["reasoning"])

        # Build the inputs dict; structure depends on whether a
        # proposed_caution accompanies the choice. NoAction emits
        # a minimal inputs (no proposed_caution); the four propose-*
        # choices embed the proposed tuple.
        extra_inputs: dict[str, Any] = {
            "confidence_band": confidence_band,
            # informed_by_decision_id reserved for v2 (DecisionLookup
            # port deferred per design memo Watch #14). Always None
            # at v1; field stays in the schema for forward-compat.
            "informed_by_decision_id": None,
        }
        if choice != "NoAction":
            proposed = parsed.get("proposed_caution")
            if proposed is None:
                # Schema violation that the adapter's tool-use enforcement
                # missed. Treat as deferred so we keep the audit invariant.
                log.warning(
                    "caution_drafter.proposed_caution_missing",
                    choice=choice,
                )
                await self._write_noaction_deferred(
                    decision_id=decision_id,
                    actor=actor,
                    run_id=run_id,
                    terminal_event=terminal_event,
                    error_class="SchemaViolation",
                    log=log,
                )
                return
            if not _proposed_target_in_candidates(proposed, valid_target_ids):
                log.warning(
                    "caution_drafter.hallucinated_target",
                    choice=choice,
                    proposed_target_id=str(proposed.get("target_id")),
                )
                await self._write_noaction_deferred(
                    decision_id=decision_id,
                    actor=actor,
                    run_id=run_id,
                    terminal_event=terminal_event,
                    error_class="HallucinatedTarget",
                    log=log,
                )
                return
            extra_inputs["proposed_caution"] = _coerce_proposed_caution(proposed)

        await self._compose_and_append(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=terminal_event,
            choice=choice,
            confidence=confidence,
            reasoning=reasoning,
            extra_inputs=extra_inputs,
            outcome="proposed" if choice != "NoAction" else "no_action",
            log=log,
        )

    async def _write_noaction_deferred(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        error_class: str,
        log: Any,
    ) -> None:
        """LLM-exhaust fallback: NoAction Decision with failure marker.

        Mirrors RunDebriefer's DebriefDeferred pattern (parallel
        v1 simplification). Confidence omitted (no LLM probability
        to report); operators reading the Decision know to re-trigger
        manually when re-draft slice ships.
        """
        await self._compose_and_append(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=terminal_event,
            choice="NoAction",
            confidence=None,
            reasoning=(
                f"LLM call failed with {error_class}; CautionDrafter "
                "deferred. Operator may re-trigger via the agent's MCP "
                "tool when a re-draft path ships."
            ),
            extra_inputs={
                "confidence_band": "low",
                "informed_by_decision_id": None,
                "failure_error_class": error_class,
            },
            outcome="deferred",
            log=log,
        )

    async def _compose_and_append(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        choice: str,
        confidence: float | None,
        reasoning: str,
        extra_inputs: dict[str, Any],
        outcome: str,
        log: Any,
    ) -> None:
        """Compose `DecisionRegistered` inline and append.

        Mirrors `RunDebrieferSubscriber._compose_and_append` shape
        verbatim (cross-BC import boundary respected: only
        `cora.decision.aggregates`, never `cora.decision.features`).

        ConcurrencyError on deterministic-id stream = a prior
        `apply()` succeeded; treat as success (at-most-once via
        deterministic id).
        """
        decision_choice = DecisionChoice(choice)
        decision_context = DecisionContext(DECISION_CONTEXT_CAUTION_PROPOSAL)
        rule = DecisionRule(_DECISION_RULE)
        inputs = validate_inputs(
            {
                "run_id": str(run_id),
                "terminal_event_id": str(terminal_event.event_id),
                "terminal_event_type": terminal_event.event_type,
                "prompt_template_id": str(CAUTION_DRAFTER_PROMPT_TEMPLATE_ID),
                **extra_inputs,
            }
        )
        validated_reasoning = validate_reasoning(reasoning)
        validated_confidence = validate_confidence(confidence)

        domain_event = DecisionRegistered(
            decision_id=decision_id,
            actor_id=actor.id,
            context=decision_context.value,
            choice=decision_choice.value,
            parent_id=None,
            override_kind=None,
            rule=rule.value,
            reasoning=validated_reasoning,
            confidence=validated_confidence,
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=(),
            inputs=inputs,
            reasoning_signature=None,
            occurred_at=terminal_event.occurred_at,
        )

        new_event = to_new_event(
            event_type=event_type_name(domain_event),
            payload=to_payload(domain_event),
            occurred_at=domain_event.occurred_at,
            event_id=uuid5(decision_id, "event:0"),
            command_name=_COMMAND_NAME,
            correlation_id=terminal_event.correlation_id,
            causation_id=terminal_event.event_id,
            principal_id=actor.id,
        )

        new_event = await self._maybe_sign(new_event, actor=actor)

        try:
            await self.event_store.append(
                stream_type=_STREAM_TYPE,
                stream_id=decision_id,
                expected_version=0,
                events=[new_event],
            )
        except ConcurrencyError:
            log.info("caution_drafter.already_processed", outcome=outcome)
            return

        log.info("caution_drafter.success", outcome=outcome, choice=choice)

    async def _maybe_sign(self, new_event: NewEvent, *, actor: Actor) -> NewEvent:
        """Attach signature/signature_kid when the kernel is configured
        with a `Signer` AND the event type is in SIGNED_EVENT_TYPES.

        No-op when `self.signer is None` (no production adapter today;
        unsigned rows are the legitimate default per design lock errata
        2026-05-24). The subscriber emits Agent-actor events
        exclusively, so the actor-discrimination check that
        `register_decision` would need is implicit here.
        """
        if self.signer is None or new_event.event_type not in SIGNED_EVENT_TYPES:
            return new_event
        signature, kid, _signing_version = await self.signer.sign(
            event_type=new_event.event_type,
            payload=new_event.payload,
            actor_id=actor.id,
        )
        return replace(new_event, signature=signature, signature_kid=kid)


def _proposed_target_in_candidates(proposed: Any, valid_target_ids: frozenset[UUID]) -> bool:
    """True iff `proposed["target_id"]` parses as a UUID present in `valid_target_ids`.

    The schema's `enum` for target_id is meant to constrain the LLM
    to a closed set, but structured-output adapters sometimes elide
    enum checks for UUID-typed properties, and a misconfigured /
    poisoned LLM can return arbitrary values. Defensive: missing /
    non-string / unparseable / unknown -> False. Caller falls back
    to NoAction-deferred on a False return.
    """
    if not isinstance(proposed, dict):
        return False
    raw = proposed.get("target_id")
    if not isinstance(raw, str):
        return False
    try:
        parsed = UUID(raw)
    except (ValueError, TypeError):
        return False
    return parsed in valid_target_ids


def _coerce_proposed_caution(proposed: Any) -> dict[str, Any]:
    """Coerce the LLM's proposed_caution dict to a JSON-safe shape.

    Tags is the only nested list; everything else is primitives.
    UUIDs from the LLM arrive as strings (per schema); kept as
    strings in the Decision payload so the round-trip is byte-stable.
    """
    if not isinstance(proposed, dict):
        msg = f"proposed_caution must be a dict, got {type(proposed).__name__}"
        raise ValueError(msg)
    coerced: dict[str, Any] = {
        "target_kind": str(proposed["target_kind"]),
        "target_id": str(proposed["target_id"]),
        "category": str(proposed["category"]),
        "severity": str(proposed["severity"]),
        "title": str(proposed["title"]),
        "body": str(proposed["body"]),
        "tags": [str(t) for t in proposed.get("tags", [])],
    }
    if proposed.get("supersedes_caution_id") is not None:
        coerced["supersedes_caution_id"] = str(proposed["supersedes_caution_id"])
    return coerced


def make_caution_drafter_subscriber(deps: Kernel) -> CautionDrafterSubscriber:
    """Construct the subscriber from the Kernel.

    Raises `RuntimeError` if `kernel.llm is None` (subscriber is
    useless without an LLM). Conditional-registration shim in
    `cora.agent._subscribers.register_agent_subscribers` short-
    circuits with a warning so this only fires for misconfigured
    callers that bypass that shim.
    """
    if deps.llm is None:
        msg = (
            "CautionDrafterSubscriber requires kernel.llm to be set; "
            "configure ANTHROPIC_API_KEY or inject a FakeLLM."
        )
        raise RuntimeError(msg)
    return CautionDrafterSubscriber(
        event_store=deps.event_store,
        llm=deps.llm,
        caution_lookup=deps.caution_lookup,
        signer=deps.signer,
    )


__all__ = [
    "CautionDrafterSubscriber",
    "make_caution_drafter_subscriber",
]
