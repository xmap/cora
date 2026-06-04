"""RunDebriefer subscriber: CORA's first side-effecting subscriber.

Subscribes to the four terminal Run events (`RunCompleted`,
`RunAborted`, `RunStopped`, `RunTruncated`), loads the terminated
Run, asks the LLM for a structured Decision (choice + confidence
+ reasoning), and emits one `DecisionRegistered` per terminal
event.

## Side-effecting subscriber pattern (NEW)

The existing projection-worker framework was designed for
read-model writes; the worker's `apply(event, conn)` runs inside
a bookmark-advance transaction with the supplied connection. A
side-effecting subscriber that writes NEW events through the
event store has two challenges:

  1. `PostgresEventStore.append` acquires its own pool connection.
     Decision writes commit in a SEPARATE transaction from the
     bookmark advance. Exact-once is not achievable across these
     two transactions.

  2. The bookmark transaction holds for the duration of `apply()`
     including the LLM call. RunDebriefer declares `batch_size = 1`
     on the class (enforced by the worker via
     `getattr(subscriber, "batch_size", DEFAULT_BATCH_SIZE)`), so the
     transaction holds one connection for at most one terminal event's
     LLM round-trip (~5-15 s). Acceptable for pilot scale (~few
     Runs/day); watch item for facility scale → split off a
     `ReactionWorker` with its own pool budget.

Mitigation (1): the Decision's `stream_id` is derived
deterministically from `terminal_event.event_id` via UUIDv5 (see
`_derive_decision_id`). If the bookmark advance fails AFTER the
Decision write succeeds (crash, network, asyncio cancellation),
the event re-fires on the next worker pass and we retry the
Decision write with the SAME `stream_id`. `EventStore.append`
with `expected_version=0` then raises `ConcurrencyError`, which
the subscriber catches and treats as success (the Decision was
already written). At-most-once is preserved.

## DebriefDeferred fallback

When the LLM call fails (after the Anthropic SDK's own internal
retries), the subscriber writes a `DecisionRegistered` with
`choice="DebriefDeferred"` and a reasoning string summarising the
failure. This preserves the exactly-one-Decision-per-terminal-Run
audit invariant (operators can see which Runs the agent couldn't
debrief and decide whether to re-trigger manually).

Per design memo lock #48, the "3 outer retries before
DebriefDeferred" pattern requires cross-`apply()`-call retry-
count tracking (which would need a new persistent table). v1
simplifies to "write DebriefDeferred on the first LLM exhaust".
The Anthropic SDK's `max_retries=2` inside one `apply()` call
gives 3 attempts already; the simplification trades cross-process
retry resilience for implementation simplicity. Watch item for
when operator-rated `misleading` correlates with transient LLM
errors.

## Read scope (v1)

The subscriber loads ONLY the Run aggregate via `load_run`. The
broader read scope (RunReading + ConduitTraversal logbook entries
+ bound Subject/Plan/Method/Practice + acknowledged Cautions +
sibling-Run comparison) is deferred per design memo lock; trigger
is "operators rate v1 Debriefs as misleading citing absent
context".

## Authorize + actor gate

The subscriber does NOT call the `Authorize` port. The agent's
permission to register Decisions is granted at Agent definition
time (the `define_agent` slice's `principal_id` was an admin
who authorised the agent's existence). Per-call authorization is
an HTTP-handler concern; subscribers are internal workers running
under the agent's identity.

The subscriber DOES gate on the agent's `Actor.active` flag
(per security gate-review convention): an operator deactivating the agent's
Actor takes effect on the next `apply()` (the worker reloads the
Actor every pass; an in-flight pass completes). The Agent
aggregate's lifecycle status (Defined / Versioned / Deprecated)
is NOT checked here -- watch item -- because requiring an extra
event-store load per terminal event has measurable cost at
facility scale and the Actor.active hop closes the same
revoke-the-agent operator gesture.

## LogbookMirror

If `kernel.logbook_mirror` is set (no production implementor today),
the subscriber calls `mirror_decision` AFTER the Decision
write commits. Fire-and-forget per the port contract; mirror
errors never propagate.

## API key redaction

The Anthropic SDK error messages may carry the API key in
diagnostic output (defensive against a future SDK regression).
`_redact_secrets` strips `sk-ant-*` substrings from any LLM
error message before structured-logging it (per security gate-review
convention).

## Duplication-by-design with `regenerate_run_debrief` slice

`_compose_and_append` here and
`cora.agent.features.regenerate_run_debrief.decider.decide` use the same
Decision BC public validators + `DecisionRegistered` constructor.
The subscriber inlines the composition (its at-most-once depends
on a deterministic decision_id derived from terminal_event.event_id
+ a UUID5 namespace, distinct from the operator-triggered slice's
fresh UUIDv7 from the IdGenerator). The slice extracts a pure
`decide()` because the slice-contract test requires `decider.py`.

The shared logic is ~25 lines. **DRY-extract trigger**: when EITHER
a third consumer of the same composition appears (Pattern B per-
anomaly subscriber, second on-demand agent slice) OR the
subscriber's at-most-once scheme converges with the slice's
(eg. both move to IdempotencyStore-keyed dedup). Pre-trigger: live
with the duplication, documented here + at
`cora.agent.features.regenerate_run_debrief.decider`.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent._subscriber_lease import attempt_debrief_lease
from cora.agent.prompts import (
    RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
    RunDebriefPayload,
    build_run_debrief_chat_request,
)
from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME
from cora.agent.subscribers._terminal_run_helpers import (
    extract_interrupted_at,
    extract_reason,
)
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
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
from cora.run.aggregates.run import load_run

if TYPE_CHECKING:
    from cora.access.aggregates.actor import Actor
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import LLM, LogbookMirror, Signer
    from cora.infrastructure.ports.event_store import EventStore, NewEvent, StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RunDebrieferSubscriber"
_DECISION_RULE = "agent:RunDebriefer:v1"

# Stable namespace for deriving deterministic Decision IDs from
# terminal Run event IDs. UUIDv5(namespace, terminal_event_id) ->
# Decision.stream_id. The namespace is generated once and pinned
# here; changing it invalidates every prior deterministic id (so
# don't).
_RUN_DEBRIEF_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000aaaa0002")

# Terminal Run events this subscriber listens to. The four match
# the design memo lock; the set does NOT include `RunHeld` /
# `RunResumed` (those are mid-lifecycle, not terminal).
_TERMINAL_RUN_EVENTS = frozenset(
    {
        "RunCompleted",
        "RunAborted",
        "RunStopped",
        "RunTruncated",
    }
)

# Regex used to strip Anthropic API-key-shaped substrings from
# error messages before structured-logging them. The key format is
# `sk-ant-` + base64-ish chars; matching aggressively because a
# false-positive redaction (eg. a string that happens to look like
# a key but isn't) costs nothing and a missed redaction costs a
# permanent log-line leak. Per security gate-review convention.
_API_KEY_LIKE_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")
_REDACTED_TOKEN = "[REDACTED]"

_log = get_logger(__name__)


def redact_secrets(message: str) -> str:
    """Strip Anthropic API-key-like substrings from a log line.

    Defensive: the SDK SHOULD never embed the key in its error
    text, but a future regression that does would persist the key
    to logs forever (events INSERT-only). Sanitise here so the
    redaction is in CORA's audit boundary, not relying on the
    vendor.

    Public callable: used by both this subscriber and the
    `regenerate_run_debrief` handler for parallel error-logging redaction.
    """
    return _API_KEY_LIKE_PATTERN.sub(_REDACTED_TOKEN, message)


# Backward-compat alias retained for the existing test that pins
# the private name. The public name `redact_secrets` is the one
# to use going forward; the alias is dropped at the rule-of-three
# trigger (third consumer or first second-agent ship).
_redact_secrets = redact_secrets


def _derive_decision_id(terminal_event_id: UUID) -> UUID:
    """Deterministic Decision id from terminal event id (UUIDv5).

    Stable across retries so a second `append()` attempt hits
    `expected_version=0` against an existing stream and raises
    `ConcurrencyError`, which the subscriber treats as a no-op.
    """
    return uuid5(_RUN_DEBRIEF_DECISION_NAMESPACE, str(terminal_event_id))


# Extractors hoisted to `_terminal_run_helpers` (rule-of-three);
# imported above as `extract_reason` / `extract_interrupted_at`.


class RunDebrieferSubscriber:
    """Reaction: terminal Run -> one advisory Decision.

    Constructed by `make_run_debriefer_subscriber` from the Kernel;
    satisfies the `Reaction` Protocol (and the `Subscriber` primitive
    it extends) structurally.

    Holds references to the LLM port and event store. The Decision's
    `actor_id` is the seeded RunDebriefer Agent's id (== that agent's
    Actor.id per 8f-a's identity-sharing invariant).

    `name`, `subscribed_event_types`, and `batch_size` are plain
    class-level constants (matches the wider Subscriber convention;
    the Reaction Protocol declares them as instance attrs which a
    `ClassVar`-annotated class would not satisfy structurally).

    `batch_size = 1` enforces what the original module docstring
    claimed before the framework supported per-subscriber tuning:
    the apply path includes a 5-15 s LLM call, so holding the pool
    connection across N events would starve Projection advance loops
    sharing the same pool. Worst-case TX duration is bounded to one
    LLM call.
    """

    name = "run_debriefer"
    subscribed_event_types = _TERMINAL_RUN_EVENTS
    batch_size = 1

    def __init__(
        self,
        *,
        event_store: EventStore,
        llm: LLM,
        logbook_mirror: LogbookMirror | None,
        signer: Signer | None = None,
    ) -> None:
        self.event_store = event_store
        self.llm = llm
        self.logbook_mirror = logbook_mirror
        self.signer = signer

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        """Process one terminal Run event.

        `conn` is the bookmark-advance transaction connection from
        the projection worker. The subscriber does NOT use it for
        Decision writes (those go through `event_store.append`,
        which opens its own transaction). The `conn` is retained
        in the contract for future at-least-once observability
        writes (eg. a `subscriber_attempts` table) but is unused
        at v1.
        """
        _ = conn  # see docstring; not used at v1
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
        log.info("run_debriefer.start")

        # Load Run aggregate (v1 read scope = Run only).
        run = await load_run(self.event_store, run_id)
        if run is None:
            # Run stream missing despite terminal event for it -- impossible
            # under the normal event-store invariants, but skip cleanly so a
            # corrupt fixture doesn't wedge the bookmark.
            log.warning("run_debriefer.skip.run_missing")
            return

        # Pre-load the Agent's Actor (the Decision aggregate requires
        # `actor_id` to exist in Access BC). If the agent isn't seeded
        # (bootstrap not yet run, deployment misconfigured), short-circuit
        # without writing -- the operator needs to fix the seed.
        actor = await load_actor(self.event_store, RUN_DEBRIEFER_AGENT_ID)
        if actor is None:
            log.warning(
                "run_debriefer.skip.agent_actor_missing",
                agent_id=str(RUN_DEBRIEFER_AGENT_ID),
                agent_name=RUN_DEBRIEFER_AGENT_NAME,
            )
            return

        # Operator-revocation gate (per security gate-review convention): a
        # Deactivated Agent Actor must not author new Decisions. The
        # check fires per `apply()`, so a deactivate-while-in-flight
        # only stops the NEXT terminal event; the current one
        # completes. That asymmetry is intentional -- aborting a
        # mid-LLM-call subscriber would orphan the Decision write
        # (LLM cost paid, no audit trail).
        if not actor.active:
            log.warning(
                "run_debriefer.skip.agent_actor_deactivated",
                agent_id=str(RUN_DEBRIEFER_AGENT_ID),
                agent_name=RUN_DEBRIEFER_AGENT_NAME,
            )
            return

        # Cross-agent lease (per [[project-run-debriefer-lease-design]]):
        # append a DecisionDebriefRequested marker to the Run stream
        # BEFORE the LLM call so a losing agent pays zero LLM cost. The
        # first writer wins via the existing UNIQUE(stream_type,
        # stream_id, version) primitive; losing agents see the winner
        # via the helper's re-load + emit a DebriefConflicted Decision
        # on their own Decision stream for audit visibility.
        lease_acquired, winning_agent_id = await attempt_debrief_lease(
            self.event_store,
            run_id=run_id,
            debriefer_agent_id=RUN_DEBRIEFER_AGENT_ID,
            terminal_event=event,
            occurred_at=event.occurred_at,
            command_name=_COMMAND_NAME,
        )
        if not lease_acquired:
            log.info(
                "run_debriefer.lease_lost",
                winning_agent_id=str(winning_agent_id) if winning_agent_id else None,
            )
            await self._write_debrief_conflicted(
                decision_id=decision_id,
                actor=actor,
                run_id=run_id,
                terminal_event=event,
                winning_agent_id=winning_agent_id,
                log=log,
            )
            return

        payload = RunDebriefPayload(
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
        )
        request = build_run_debrief_chat_request(payload)

        try:
            response = await self.llm.chat(request)
        except LLMError as exc:
            log.warning(
                "run_debriefer.llm_failed",
                error_class=type(exc).__name__,
                error_message=redact_secrets(str(exc)[:200]),
            )
            await self._write_debrief_deferred(
                decision_id=decision_id,
                actor=actor,
                run_id=run_id,
                terminal_event=event,
                error_class=type(exc).__name__,
                log=log,
            )
            return

        await self._write_debrief_success(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=event,
            parsed=response.parsed,
            log=log,
        )

        if self.logbook_mirror is not None:
            try:
                await self.logbook_mirror.mirror_decision(
                    decision_id=decision_id,
                    narrative=str(response.parsed.get("reasoning", "")),
                    target_logbook=run.name.value,
                )
            except Exception as exc:
                # Mirror is fire-and-forget per port contract; log but
                # do NOT propagate (mirror outage must not block the
                # Decision-emission audit trail).
                log.warning(
                    "run_debriefer.logbook_mirror_failed",
                    error_class=type(exc).__name__,
                    error_message=redact_secrets(str(exc)[:200]),
                )

    async def _write_debrief_success(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        parsed: Any,
        log: Any,
    ) -> None:
        """Compose + append the success-path Decision."""
        choice = str(parsed["choice"])
        confidence_raw = parsed["confidence"]
        reasoning_raw = str(parsed["reasoning"])
        await self._compose_and_append(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=terminal_event,
            choice=choice,
            confidence=float(confidence_raw) if confidence_raw is not None else None,
            reasoning=reasoning_raw,
            extra_inputs={},
            outcome="success",
            log=log,
        )

    async def _write_debrief_deferred(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        error_class: str,
        log: Any,
    ) -> None:
        """Compose + append the DebriefDeferred fallback Decision.

        Preserves the exactly-one-Decision-per-terminal-Run audit
        invariant when the LLM call exhausts. `confidence` is omitted
        (no LLM probability to report); operators reading the
        Decision know to re-trigger manually.
        """
        await self._compose_and_append(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=terminal_event,
            choice="DebriefDeferred",
            confidence=None,
            reasoning=(
                f"LLM call failed with {error_class}; debrief deferred. "
                "Operator may re-trigger via the agent's MCP tool when "
                "8f-c lands the on-demand path."
            ),
            extra_inputs={"failure_error_class": error_class},
            outcome="deferred",
            log=log,
        )

    async def _write_debrief_conflicted(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        winning_agent_id: UUID | None,
        log: Any,
    ) -> None:
        """Compose + append the DebriefConflicted audit Decision when
        the lease race was lost to another agent.

        Per [[project-run-debriefer-lease-design]]: losing agents emit
        a Decision on their OWN Decision stream (deterministic
        decision_id via the per-agent uuid5 namespace) citing the
        winning `debriefer_agent_id`. Recovers the only observability
        axis where the Trust.Policy alternative beat the Run-stream
        lease primitive: concurrent-debrief races stay visible in the
        Decision projection without polluting the Run stream further.

        `confidence` is omitted: there was no LLM call. `winning_agent_id`
        is None on the rare race where the Run stream version moved for
        a non-lease reason; the reasoning string degrades gracefully."""
        if winning_agent_id is not None:
            reasoning = (
                f"Lost cross-agent debrief-lease race for terminal event "
                f"{terminal_event.event_id} to agent {winning_agent_id}."
            )
            extra_inputs: dict[str, Any] = {"winning_agent_id": str(winning_agent_id)}
        else:
            reasoning = (
                f"Lost cross-agent debrief-lease race for terminal event "
                f"{terminal_event.event_id}; winning agent not identified "
                "(Run stream version advanced between load and append for "
                "a non-lease reason)."
            )
            extra_inputs = {}
        await self._compose_and_append(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=terminal_event,
            choice="DebriefConflicted",
            confidence=None,
            reasoning=reasoning,
            extra_inputs=extra_inputs,
            outcome="conflicted",
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
        """Compose `DecisionRegistered` inline and append; catch ConcurrencyError.

        The subscriber doesn't call Decision BC's slice-level
        `decide()` because that handler uses a non-deterministic
        `new_id` (we need UUID5-derived `decision_id` for at-most-
        once retry semantics). Instead it composes the event
        through the same VOs the decider uses (cross-BC import
        boundary respected: only `cora.decision.aggregates` is
        imported, never `cora.decision.features`).

        ConcurrencyError on a deterministic-id stream means a prior
        `apply()` succeeded but the bookmark advance failed; on retry
        the Decision is already there. Treat as success; bookmark
        advances on this pass.

        The Decision's `occurred_at` reuses the terminal event's
        `occurred_at` so successive retries derive the same value
        (deterministic timestamp under retry, no clock port
        consulted).
        """
        # Field validation via Decision BC's public VOs + helpers.
        # Same path the slice's decider takes; the subscriber owns
        # the duplication intentionally per the cross-BC import
        # boundary (no `features.*` import).
        decision_choice = DecisionChoice(choice)
        decision_context = DecisionContext(DECISION_CONTEXT_RUN_DEBRIEF)
        rule = DecisionRule(_DECISION_RULE)
        inputs = validate_inputs(
            {
                "run_id": str(run_id),
                "terminal_event_id": str(terminal_event.event_id),
                "terminal_event_type": terminal_event.event_type,
                "prompt_template_id": str(RUN_DEBRIEF_PROMPT_TEMPLATE_ID),
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
            # Derive event_id deterministically so retries produce
            # the same envelope id (event_store's UNIQUE(event_id)
            # also makes the second write a no-op).
            event_id=uuid5(decision_id, "event:0"),
            command_name=_COMMAND_NAME,
            correlation_id=terminal_event.correlation_id,
            # Causation chain: the agent's Decision is "caused by"
            # the terminal Run event per PROV-O wasInformedBy.
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
            log.info("run_debriefer.already_processed", outcome=outcome)
            return

        log.info("run_debriefer.success", outcome=outcome)

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
        signature, kid, signing_version = await self.signer.sign(
            event_type=new_event.event_type,
            payload=new_event.payload,
            actor_id=actor.id,
        )
        return replace(
            new_event,
            signature=signature,
            signature_kid=kid,
            signature_version=signing_version,
        )


def make_run_debriefer_subscriber(deps: Kernel) -> RunDebrieferSubscriber:
    """Construct the subscriber from the Kernel.

    Raises `RuntimeError` if `kernel.llm is None` (the subscriber
    is useless without an LLM). Composition root (`cora.api.main`)
    is responsible for ensuring `llm_factory` is wired before
    register-time. The conditional-registration shim in
    `cora.agent._subscribers.register_agent_subscribers` short-
    circuits with a warning so this only fires for misconfigured
    callers that bypass that shim.
    """
    if deps.llm is None:
        msg = (
            "RunDebrieferSubscriber requires kernel.llm to be set; "
            "configure ANTHROPIC_API_KEY or inject a FakeLLM."
        )
        raise RuntimeError(msg)
    return RunDebrieferSubscriber(
        event_store=deps.event_store,
        llm=deps.llm,
        logbook_mirror=deps.logbook_mirror,
        signer=deps.signer,
    )


__all__ = [
    "RunDebrieferSubscriber",
    "make_run_debriefer_subscriber",
]
