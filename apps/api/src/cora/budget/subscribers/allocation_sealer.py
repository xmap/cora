"""Reaction: a CampaignClosed -> seal the campaign-bound Active allocation.

The paper's close-the-books claim: an allocation whose `campaign_id`
references the closed Campaign is sealed automatically at the same
instant the experiment's own books close, freezing the final-spend
snapshot beside the campaign record. An allocation with no campaign
binding (or bound to a different campaign) is untouched: binding is
what opts an envelope into the automatic seal, so beamline-total
envelopes without a campaign stay under manual `seal_allocation`.

## Authz posture: system actor, raw decide + append (not the handler)

The seal must carry a principal, and no operator issued this command.
Precedents inspected: the LLM subscribers and the kill-switch write
as their own SEEDED agent principals (each is a modeled Agent with an
Actor and, under real Trust, an operator-granted policy), while
seed/bootstrap writes and the enclosure permit monitor stamp
`SYSTEM_PRINCIPAL_ID` and run the slice's load -> decide -> append
WITHOUT the handler's authorize gate, because `SYSTEM_PRINCIPAL_ID`
is deliberately NOT an authz wildcard and a real Trust policy would
deny it. This sealer is a deterministic bookkeeping reflex, not an
agent with judgment worth modeling, so it mirrors the enclosure
monitor: `sealed_by = SYSTEM_PRINCIPAL_ID`, same-BC decider reuse
(the Active-only guard in `seal_allocation.decider` is the real
gate), no Authorize call. The spend snapshot flows through the SAME
`make_ledger_total_spend` reader `wire_budget` binds, so an automatic
seal and an operator seal can never disagree about the figure.

## Determinism + idempotency

The seal's `occurred_at` and its ledger window end are the
CampaignClosed event's `occurred_at`, not wall clock, so a replayed
delivery derives the same event (the subscribers' determinism rule).
The seal event's `event_id` is a UUIDv5 of (trigger event, allocation)
and the append is guarded by the loaded stream version. A benign
concurrent write (an operator `amend_allocation_ceiling` landing
between load and append) bumps the version while the envelope is
still Active, so instead of forfeiting the automatic seal the sealer
re-loads and retries the append at the fresh version (bounded, a few
attempts); the deterministic event id keeps the retry idempotent. A
re-delivery after a real seal short-circuits on the non-Active fold
pre-guard. Skips (no Active envelope, unbound envelope, campaign
mismatch, retry exhaustion) advance the bookmark; nothing here may
wedge it.

## Lookup + fold double-check, and the projection-lag caveat

`AllocationLookup.find_active` (projection-backed) finds the
candidate cheaply, then the aggregate stream is loaded and folded
before deciding: the fold is the truth the optimistic append is
versioned against. The double-check guards the stale-POSITIVE
direction (projection still shows Active, fold says otherwise) and
logs it at WARNING as a real divergence. It cannot guard the
stale-NEGATIVE direction: because subscribers run on independent
cursors, the summary projection may not yet reflect an
`AllocationActivated` that landed just before CampaignClosed, so a
`no_active_allocation` or `campaign_mismatch` skip can be a false
negative. A missed automatic seal is recovered by the operator's
manual `seal_allocation` slice, which reads the stream directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.budget.aggregates.allocation import (
    AllocationStatus,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.budget.features.seal_allocation import (
    SealAllocation,
    decide,
    make_ledger_total_spend,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import AllocationLookup, SpendLookup
    from cora.infrastructure.ports.event_store import EventStore, StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_STREAM_TYPE = "Allocation"
_COMMAND_NAME = "AllocationSealerSubscriber"
_TRIGGER_EVENT_TYPE = "CampaignClosed"

# Stable namespace for deriving the seal event's id from the
# (CampaignClosed event, allocation) pair, following the sibling
# suffix convention (cf. aaaa0002 / bbbb0002 / b1110002) in the
# sealer's own a10c block. A re-delivered CampaignClosed derives the
# same id, so the event store's UNIQUE(event_id) backs up the
# expected-version guard.
_ALLOCATION_SEALER_NAMESPACE = UUID("01900000-0000-7000-8000-0000a10c0002")

_MAX_SEAL_ATTEMPTS = 3
"""Bounded reload-and-retry on a lost seal race. A benign concurrent
writer (an operator amend while the envelope is still Active) bumps the
stream version; rather than forfeit the automatic seal, the sealer
re-loads and retries at the fresh version. Three attempts covers the
realistic burst; beyond it the seal is deferred to the manual slice."""

_log = get_logger(__name__)


class AllocationSealerSubscriber:
    """Reaction: CampaignClosed -> seal the allocation bound to that campaign.

    Constructed by `make_allocation_sealer_subscriber` from the
    Kernel; satisfies the `Reaction` Protocol structurally.
    Deterministic (no LLM); `batch_size = 1` keeps the per-event
    load + ledger fold + append sequence inside one small bookmark
    transaction, matching the sibling Reactions.
    """

    name = "allocation_sealer"
    subscribed_event_types = frozenset({_TRIGGER_EVENT_TYPE})
    batch_size = 1

    def __init__(
        self,
        *,
        event_store: EventStore,
        allocation_lookup: AllocationLookup,
        spend_lookup: SpendLookup,
    ) -> None:
        self.event_store = event_store
        self.allocation_lookup = allocation_lookup
        self._total_spend_reader = make_ledger_total_spend(spend_lookup)

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        """Process one CampaignClosed; seal its bound Active allocation, if any."""
        # conn unused: the seal goes through the event store, like the
        # other side-effecting subscribers.
        _ = conn
        if event.event_type != _TRIGGER_EVENT_TYPE:
            return

        closed_campaign_id = UUID(event.payload["campaign_id"])
        log = _log.bind(
            subscriber=self.name,
            command_name=_COMMAND_NAME,
            campaign_id=str(closed_campaign_id),
            trigger_event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )

        active = await self.allocation_lookup.find_active()
        if active is None:
            log.info("allocation_sealer.skip.no_active_allocation")
            return
        if active.campaign_id != closed_campaign_id:
            log.info(
                "allocation_sealer.skip.campaign_mismatch",
                allocation_id=str(active.allocation_id),
                bound_campaign_id=(
                    str(active.campaign_id) if active.campaign_id is not None else None
                ),
            )
            return

        allocation_id = active.allocation_id
        for attempt in range(_MAX_SEAL_ATTEMPTS):
            stored, current_version = await self.event_store.load(
                stream_type=_STREAM_TYPE,
                stream_id=allocation_id,
            )
            state = fold([from_stored(s) for s in stored])
            if state is None or state.status is not AllocationStatus.ACTIVE:
                # Fold disagrees with the projection that named this
                # candidate Active: a stale-positive projection row, or a
                # replayed delivery after the seal already landed. Either
                # way the window is closed; the divergence is worth a
                # WARNING (the projection is behind its own stream).
                log.warning(
                    "allocation_sealer.skip.not_active",
                    allocation_id=str(allocation_id),
                    status=(str(state.status) if state is not None else None),
                )
                return
            if state.campaign_id != closed_campaign_id:
                # The stream rebound to another campaign since the
                # projection read; not this CampaignClosed's envelope.
                log.info(
                    "allocation_sealer.skip.campaign_mismatch_on_fold",
                    allocation_id=str(allocation_id),
                    bound_campaign_id=(
                        str(state.campaign_id) if state.campaign_id is not None else None
                    ),
                )
                return

            window_start = state.activated_at
            assert window_start is not None  # Active state always folds activated_at
            spent_usd = await self._total_spend_reader(
                window_start=window_start,
                window_end=event.occurred_at,
            )

            command = SealAllocation(
                allocation_id=state.id,
                reason=f"Campaign {closed_campaign_id} closed; books sealed automatically.",
            )
            domain_events = decide(
                state=state,
                command=command,
                now=event.occurred_at,
                spent_usd=spent_usd,
                sealed_by=ActorId(SYSTEM_PRINCIPAL_ID),
            )
            new_events = [
                to_new_event(
                    event_type=event_type_name(domain_event),
                    payload=to_payload(domain_event),
                    occurred_at=domain_event.occurred_at,
                    event_id=uuid5(
                        _ALLOCATION_SEALER_NAMESPACE,
                        f"seal:{event.event_id}:{state.id}",
                    ),
                    command_name=_COMMAND_NAME,
                    correlation_id=event.correlation_id,
                    causation_id=event.event_id,
                    principal_id=SYSTEM_PRINCIPAL_ID,
                )
                for domain_event in domain_events
            ]
            try:
                await self.event_store.append(
                    stream_type=_STREAM_TYPE,
                    stream_id=state.id,
                    expected_version=current_version,
                    events=new_events,
                )
            except ConcurrencyError:
                # The stream advanced between load and append. If a benign
                # writer (an operator amend) bumped the version while the
                # envelope is still Active, re-load and retry; the
                # deterministic event id keeps this idempotent. A concurrent
                # seal or void lands the next iteration on the non-Active
                # pre-guard and returns.
                if attempt + 1 < _MAX_SEAL_ATTEMPTS:
                    log.info(
                        "allocation_sealer.seal_conflict_retry",
                        allocation_id=str(state.id),
                        attempt=attempt,
                    )
                    continue
                log.warning(
                    "allocation_sealer.skip.seal_retries_exhausted",
                    allocation_id=str(state.id),
                )
                return

            log.info(
                "allocation_sealer.sealed",
                allocation_id=str(state.id),
                spent_usd=spent_usd,
            )
            return


def make_allocation_sealer_subscriber(deps: Kernel) -> AllocationSealerSubscriber:
    """Build the allocation sealer closed over the shared deps."""
    return AllocationSealerSubscriber(
        event_store=deps.event_store,
        allocation_lookup=deps.allocation_lookup,
        spend_lookup=deps.spend_lookup,
    )


__all__ = [
    "AllocationSealerSubscriber",
    "make_allocation_sealer_subscriber",
]
