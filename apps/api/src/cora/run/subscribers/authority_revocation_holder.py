"""Reaction: on a revoked grant, HOLD the revoked principal's in-flight runs.

The authority-revocation kill-switch. Reacts to Trust's `PolicyGrantRevoked`
and, for the principal whose grant was removed, holds every run that
principal is still behind (started or supervises) so a withdrawn actor,
human or agent, cannot leave work running unattended. Holding is
reversible: the run lands in a defined `Held` state a human can take over
or resume, never aborted.

## Identity: SYSTEM, not an agent

The holder acts as `SYSTEM_PRINCIPAL_ID`, the canonical infrastructure
principal, NOT a seeded Agent. RunSupervisor / CautionPromoter are seeded
Agents because they are DECIDERS with lifecycle; this holder is a
deterministic reflex ("authority withdrawn -> park the work"), so it is
plain infrastructure. It records `DecisionRegistered(decided_by=SYSTEM,
context=AuthorityRevocation, choice=Hold)` per held run, then issues
`HoldRun` as SYSTEM. There is no `actor.active` gate (SYSTEM is a bare
principal, not a registered Actor); the off-switch is
`settings.authority_revocation_holder_enabled` (the subscriber is
registered only when enabled).

## Cross-BC, eventually consistent

`revoke_grant` writes only the Policy stream; this Reaction reacts to the
committed `PolicyGrantRevoked` and issues independent `HoldRun` commands
(no cross-BC atomic write, no cascade in the decider). A brief window
exists where the principal is revoked but a run is still Running until the
hold lands; that is acceptable because the PDP already denies the revoked
principal's NEW actions and the hold is reversible.

## Idempotency

The compensation Decision id is a deterministic uuid5 of
`(source event id, run id)`, appended at `expected_version=0`; re-delivery
is a `ConcurrencyError` no-op. `HoldRun` is itself Running-only, so a run
already Held or terminal is a benign `RunCannotHoldError` / `RunNotFoundError`
no-op. The apply body never raises: a poison event must not wedge the
shared projection-worker bookmark.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_AUTHORITY_REVOCATION,
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
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_PRINCIPAL_ID
from cora.run.aggregates.run.state import RunCannotHoldError, RunNotFoundError
from cora.run.errors import UnauthorizedError
from cora.run.features.hold_run.command import HoldRun
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import Clock, IdGenerator
    from cora.infrastructure.ports.event_store import EventStore, StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike
    from cora.run.features.hold_run.handler import Handler as HoldRunHandler
    from cora.run.ports import RunActorInvolvementLookup

_DECISION_STREAM_TYPE = "Decision"
_COMMAND_NAME = "AuthorityRevocationHolder"
_DECISION_RULE = "system:AuthorityRevocationHolder:v1"
_TRIGGER_EVENT_TYPE = "PolicyGrantRevoked"
_HOLD_CHOICE = "Hold"

# Stable namespace for deriving the compensation Decision id from the
# (source event, run) pair. Distinct from the agent namespaces (dddd block)
# and the run BC's other derivations.
_AUTHORITY_REVOCATION_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000eeee0001")

_log = get_logger(__name__)


def _derive_decision_id(source_event_id: UUID, run_id: UUID) -> UUID:
    """Deterministic compensation-Decision id for one held run.

    Keyed on both the source PolicyGrantRevoked event and the run so each
    (revocation, run) pair gets exactly one Decision, and re-delivery of
    the same revocation re-derives the same ids (ConcurrencyError no-op).
    """
    return uuid5(_AUTHORITY_REVOCATION_DECISION_NAMESPACE, f"{source_event_id}:{run_id}")


class AuthorityRevocationHolderSubscriber:
    """Holds a revoked principal's in-flight runs (the kill-switch)."""

    name = "authority_revocation_holder"
    subscribed_event_types = frozenset({_TRIGGER_EVENT_TYPE})
    batch_size = 1

    def __init__(
        self,
        *,
        event_store: EventStore,
        hold_run: HoldRunHandler,
        involvement_lookup: RunActorInvolvementLookup,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self.event_store = event_store
        self.hold_run = hold_run
        self.involvement_lookup = involvement_lookup
        self.clock = clock
        self.id_generator = id_generator

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        _ = conn  # cross-BC writes use their own pool connection, not this one
        if event.event_type != _TRIGGER_EVENT_TYPE:
            return
        try:
            await self._handle_revocation(event)
        except Exception:
            _log.exception(
                "authority_revocation_holder.apply_failed",
                event_id=str(event.event_id),
            )

    async def _handle_revocation(self, event: StoredEvent) -> None:
        payload = event.payload
        revoked_principal_id = UUID(payload["revoked_principal_id"])
        policy_id = UUID(payload["policy_id"])

        run_ids = await self.involvement_lookup.find_inflight_run_ids(revoked_principal_id)
        if not run_ids:
            return

        # Deterministic order so re-derivation is stable across retries.
        for run_id in sorted(run_ids):
            decision_id = _derive_decision_id(event.event_id, run_id)
            recorded = await self._record_hold_decision(
                decision_id=decision_id,
                run_id=run_id,
                revoked_principal_id=revoked_principal_id,
                policy_id=policy_id,
                source_event_id=event.event_id,
            )
            if not recorded:
                # A prior delivery already wrote this (revocation, run) Decision.
                # Skipping the hold here is safe ONLY because bookmark-tied
                # redelivery implies the hold has not been stranded: the worker
                # advances the bookmark AFTER apply() returns, so a redelivery
                # of this event means a prior apply() did not complete, which
                # means either the hold already landed (run now Held; a fresh
                # hold would be a benign RunCannotHoldError no-op anyway) or the
                # Decision committed but the process died before the hold, in
                # which case the run is still Running and THIS delivery will not
                # reach here (the Decision append succeeds on the first delivery
                # that commits it, and that same delivery issues the hold below).
                # The one residual is an unexpected non-benign error from
                # _issue_hold after the Decision commits; that is swallowed by
                # apply()'s guard and recovered via dismiss_event_in_reaction.
                continue
            await self._issue_hold(run_id=run_id, decision_id=decision_id)

    async def _record_hold_decision(
        self,
        *,
        decision_id: UUID,
        run_id: UUID,
        revoked_principal_id: UUID,
        policy_id: UUID,
        source_event_id: UUID,
    ) -> bool:
        """Append the compensation Decision; False on ConcurrencyError (done)."""
        now = self.clock.now()
        domain_event = DecisionRegistered(
            decision_id=decision_id,
            decided_by=ActorId(SYSTEM_PRINCIPAL_ID),
            context=DecisionContext(DECISION_CONTEXT_AUTHORITY_REVOCATION).value,
            choice=DecisionChoice(_HOLD_CHOICE).value,
            parent_id=None,
            override_kind=None,
            rule=DecisionRule(_DECISION_RULE).value,
            reasoning=validate_reasoning("Authority revoked; holding the actor's in-flight run."),
            confidence=validate_confidence(None),
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=(),
            inputs=validate_inputs(
                {
                    "run_id": str(run_id),
                    "revoked_principal_id": str(revoked_principal_id),
                    "policy_id": str(policy_id),
                    "source_event_id": str(source_event_id),
                }
            ),
            reasoning_signature=None,
            occurred_at=now,
        )
        new_event = to_new_event(
            event_type=event_type_name(domain_event),
            payload=to_payload(domain_event),
            occurred_at=now,
            event_id=uuid5(decision_id, "event:0"),
            command_name=_COMMAND_NAME,
            correlation_id=self.id_generator.new_id(),
            causation_id=None,
            principal_id=SYSTEM_PRINCIPAL_ID,
        )
        try:
            await self.event_store.append(
                stream_type=_DECISION_STREAM_TYPE,
                stream_id=decision_id,
                expected_version=0,
                events=[new_event],
            )
        except ConcurrencyError:
            _log.info(
                "authority_revocation_holder.decision_already_written",
                run_id=str(run_id),
            )
            return False
        return True

    async def _issue_hold(self, *, run_id: UUID, decision_id: UUID) -> None:
        """Issue HoldRun as SYSTEM; benign no-op if the run cannot be held."""
        try:
            await self.hold_run(
                HoldRun(run_id=run_id, decided_by_decision_id=decision_id),
                principal_id=SYSTEM_PRINCIPAL_ID,
                correlation_id=self.id_generator.new_id(),
                surface_id=NIL_SENTINEL_ID,
            )
        except (RunCannotHoldError, RunNotFoundError) as exc:
            # Already Held / terminal / gone between lookup and issue: benign.
            _log.info(
                "authority_revocation_holder.hold_skipped",
                run_id=str(run_id),
                reason=type(exc).__name__,
            )
        except UnauthorizedError:
            # The SAFETY reflex failed: SYSTEM is not granted HoldRun in the
            # operator's policy, so a revoked actor's run keeps RUNNING while
            # the audit Decision already says "held". This is a deployment
            # misconfiguration, not a benign race (contrast RunSupervisor,
            # where a missed hold is a deferred optimization). Log at ERROR
            # with a stable, alertable key; enabling this subscriber under
            # TrustAuthorize REQUIRES SYSTEM_PRINCIPAL_ID granted HoldRun.
            _log.error(
                "authority_revocation_holder.hold_unauthorized",
                run_id=str(run_id),
                remediation=(
                    "grant SYSTEM_PRINCIPAL_ID the HoldRun command in the configured Trust policy"
                ),
            )


def make_authority_revocation_holder_subscriber(
    deps: Kernel,
) -> AuthorityRevocationHolderSubscriber:
    """Build the holder subscriber closed over shared deps.

    The involvement lookup is Postgres-backed when a pool is present, else
    the in-memory stub (app_env=test), mirroring `_default_channel_lookup`.
    """
    from cora.run.adapters import PostgresRunActorInvolvementLookup
    from cora.run.features import hold_run
    from cora.run.ports import InMemoryRunActorInvolvementLookup

    involvement_lookup = (
        PostgresRunActorInvolvementLookup(deps.pool)
        if deps.pool is not None
        else InMemoryRunActorInvolvementLookup()
    )
    return AuthorityRevocationHolderSubscriber(
        event_store=deps.event_store,
        hold_run=hold_run.bind(deps),
        involvement_lookup=involvement_lookup,
        clock=deps.clock,
        id_generator=deps.id_generator,
    )


__all__ = [
    "AuthorityRevocationHolderSubscriber",
    "make_authority_revocation_holder_subscriber",
]
