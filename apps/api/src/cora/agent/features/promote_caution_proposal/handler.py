"""Application handler for the `promote_caution_proposal` slice.

Pattern C cross-BC write: the agent BC writes Caution events
DIRECTLY to the Caution BC's event stream via
`EventStore.append_streams`. Mirrors `define_agent` (which writes
`ActorRegistered` on the Access BC stream the same way).

## Why not call Caution BC's bind() factory

CORA's architecture rule (see `apps/api/tach.toml` header):

  > A BC may only reach into a sibling BC through that sibling's
  > `aggregates.*` namespace (the read-side public surface).
  > Never through `features.*` (sibling slice handlers).

The Caution aggregate already exposes everything needed for a
cross-BC write: event types (`CautionRegistered` / `CautionSuperseded`),
validating VOs (`CautionText`, `CautionWorkaround`, `CautionTag`),
state + status enums (for the supersede source-state guard), the
read helper (`load_caution`), and the envelope helpers
(`event_type_name` / `to_payload`). The handler below uses those
directly. The Caution BC's own slice handlers are not invoked.

## Field mapping (CautionDrafter prompt -> Caution event)

  - `text = title` (short summary; appears in Caution.text and the
    Run.start banner truncation)
  - `workaround = body` (the actionable narrative)
  - `expires_at`, `propagate_to_children`: not surfaced on the
    CautionDrafter prompt at v1; defaults applied (None / False).

## Idempotency

Fresh UUIDv7 per call + Brandur Idempotency-Key envelope wrapped at
wire.py (same pattern as regenerate_run_debrief). Same Idempotency-Key on
retry returns the cached caution_id; fresh key creates a new
Caution.

## Authorize

Authorize port IS called (HTTP-handler convention). Action name
`PromoteCautionProposal`.

## Errors

  - DecisionNotFoundError (404) -- load_decision returned None
  - DecisionNotCautionProposalError (400) -- wrong context
  - CautionProposalNotActionableError (400) -- choice = NoAction
  - CautionProposalMalformedError (400) -- proposed_caution invalid
  - UnauthorizedError (403) -- Authorize port denied
  - CautionNotFoundError (Caution BC) -- supersede parent missing
  - CautionCannotSupersedeError (Caution BC) -- parent not Active
  - Invalid*Error (Caution BC) -- VO validation failures
"""

from typing import Protocol
from uuid import UUID

from cora.agent.aggregates.agent import load_agent
from cora.agent.errors import (
    DecisionNotEmittedByCautionDrafterError,
    UnauthorizedError,
)
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.decider import decide
from cora.agent.seed_caution_drafter import CAUTION_DRAFTER_AGENT_KIND
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionNotFoundError,
    CautionRegistered,
    CautionSeverity,
    CautionSuperseded,
    CautionTag,
    CautionTarget,
    CautionText,
    CautionWorkaround,
    ProcedureTarget,
    ensure_expires_at_future,
    ensure_supersedable,
    ensure_target_preserved,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.caution.aggregates.caution.evolver import fold
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_CAUTION_STREAM_TYPE = "Caution"
_COMMAND_NAME = "PromoteCautionProposal"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare promote_caution_proposal handler."""

    async def __call__(
        self,
        command: PromoteCautionProposal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """promote_caution_proposal handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: PromoteCautionProposal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def _build_caution_target(target_kind: str, target_id: UUID) -> CautionTarget:
    """Map prompt `target_kind` + `target_id` to Caution BC's union."""
    if target_kind == "Asset":
        return AssetTarget(asset_id=target_id)
    if target_kind == "Procedure":
        return ProcedureTarget(procedure_id=target_id)
    msg = f"Unknown target_kind {target_kind!r}; expected 'Asset' or 'Procedure'"
    raise ValueError(msg)


def bind(deps: Kernel) -> Handler:
    """Build a promote_caution_proposal handler closed over the shared deps."""

    async def handler(
        command: PromoteCautionProposal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        log = _log.bind(
            command_name=_COMMAND_NAME,
            decision_id=str(command.decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )
        log.info("promote_caution_proposal.start")

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            log.info("promote_caution_proposal.denied", reason=authz.reason)
            raise UnauthorizedError(authz.reason)

        # Load the CautionProposal Decision; the decider validates
        # it + extracts the proposed-Caution payload.
        decision = await load_decision(deps.event_store, command.decision_id)

        # Provenance gate: the Decision must have been emitted by a
        # registered Agent of kind CautionDrafter. Decision.context +
        # choice are necessary but not sufficient (any actor able to
        # write a `DecisionRegistered` envelope with the right context
        # would otherwise be able to promote arbitrary Cautions). The
        # check uses `load_agent` against the Agent BC's event stream;
        # mirrors W3C PROV-O + FDA CDS Criterion 3 (receiver
        # re-validates attribution against the producer registry).
        # NOTE: a None decision is left to the pure decider below, which
        # raises DecisionNotFoundError; we only gate when the Decision
        # actually exists.
        if decision is not None:
            producer = await load_agent(deps.event_store, decision.decided_by)
            producer_kind = producer.kind.value if producer is not None else None
            if producer is None or producer_kind != CAUTION_DRAFTER_AGENT_KIND:
                log.info(
                    "promote_caution_proposal.provenance_failed",
                    decision_decided_by=str(decision.decided_by),
                    observed_kind=producer_kind,
                )
                raise DecisionNotEmittedByCautionDrafterError(
                    decision_id=command.decision_id,
                    actor_id=decision.decided_by,
                    observed_kind=producer_kind,
                )

        view = decide(decision, command)

        target = _build_caution_target(view.target_kind, view.target_id)
        category = CautionCategory(view.category)
        severity = CautionSeverity(view.severity)
        # VO validation: bounded-text + tag length checks. Raises
        # InvalidCautionTextError / InvalidCautionWorkaroundError /
        # InvalidCautionTagError if any field violates the contract.
        text = CautionText(view.title)
        workaround = CautionWorkaround(view.body)
        tags = frozenset(CautionTag(t).value for t in view.tags)

        new_caution_id = deps.id_generator.new_id()
        now = deps.clock.now()

        # CautionDrafter v1 does not surface expires_at on the prompt
        # (hardcoded None below). The predicate call is explicit so the
        # invariant fires the moment a future prompt iteration surfaces
        # it; the architecture pin pairs this with the import.
        expires_at = None
        ensure_expires_at_future(expires_at, now)

        if view.choice == "ProposeSupersede":
            assert view.supersedes_caution_id is not None  # decider invariant

            # Load the parent + its raw stream version (the
            # optimistic-concurrency token for the parent append).
            stored, parent_version = await deps.event_store.load(
                _CAUTION_STREAM_TYPE, view.supersedes_caution_id
            )
            parent = fold([from_stored(s) for s in stored])
            if parent is None:
                raise CautionNotFoundError(view.supersedes_caution_id)
            # Caution BC invariants applied via the shared `aggregates.caution`
            # invariants module so this cross-BC write cannot drift from the
            # native deciders. Same errors as `supersede_caution`, so HTTP
            # mapping is uniform regardless of which surface raised them.
            ensure_supersedable(parent)
            ensure_target_preserved(parent.target, target)

            parent_event = CautionSuperseded(
                caution_id=parent.id,
                superseded_by_caution_id=new_caution_id,
                occurred_at=now,
            )
            child_event = CautionRegistered(
                caution_id=new_caution_id,
                target=target,
                category=category.value,
                severity=severity.value,
                text=text.value,
                workaround=workaround.value,
                tags=tags,
                authored_by=ActorId(principal_id),
                expires_at=expires_at,
                propagate_to_children=False,
                parent_id=parent.id,
                occurred_at=now,
            )

            parent_envelope = to_new_event(
                event_type=event_type_name(parent_event),
                payload=to_payload(parent_event),
                occurred_at=now,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            child_envelope = to_new_event(
                event_type=event_type_name(child_event),
                payload=to_payload(child_event),
                occurred_at=now,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )

            log.info(
                "promote_caution_proposal.via_supersede",
                target_kind=view.target_kind,
                prior_caution_id=str(parent.id),
                new_caution_id=str(new_caution_id),
            )
            await deps.event_store.append_streams(
                [
                    StreamAppend(
                        stream_type=_CAUTION_STREAM_TYPE,
                        stream_id=parent.id,
                        expected_version=parent_version,
                        events=[parent_envelope],
                    ),
                    StreamAppend(
                        stream_type=_CAUTION_STREAM_TYPE,
                        stream_id=new_caution_id,
                        expected_version=0,
                        events=[child_envelope],
                    ),
                ]
            )
        else:
            register_event = CautionRegistered(
                caution_id=new_caution_id,
                target=target,
                category=category.value,
                severity=severity.value,
                text=text.value,
                workaround=workaround.value,
                tags=tags,
                authored_by=ActorId(principal_id),
                expires_at=expires_at,
                propagate_to_children=False,
                parent_id=None,
                occurred_at=now,
            )
            register_envelope = to_new_event(
                event_type=event_type_name(register_event),
                payload=to_payload(register_event),
                occurred_at=now,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            log.info(
                "promote_caution_proposal.via_register",
                target_kind=view.target_kind,
                new_caution_id=str(new_caution_id),
            )
            await deps.event_store.append(
                stream_type=_CAUTION_STREAM_TYPE,
                stream_id=new_caution_id,
                expected_version=0,
                events=[register_envelope],
            )

        log.info(
            "promote_caution_proposal.success",
            choice=view.choice,
            caution_id=str(new_caution_id),
        )
        return new_caution_id

    return handler
