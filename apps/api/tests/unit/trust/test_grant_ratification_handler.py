"""Application-handler unit tests for the `grant_ratification` slice (transition).

Pure-decider behavior is exercised in `ratification/test_grant_ratification_decider.py`
and the sibling PBT; here we pin the handler-level concerns: state load + event
append, the authz-deny path, and the independence (four-eyes) invariant threaded
end-to-end (the envelope principal becomes `granted_by`, so a requester granting
its own request raises).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.trust import UnauthorizedError
from cora.trust.aggregates.ratification import (
    RatificationNotFoundError,
    RatificationRequested,
    RatificationRequesterCannotSelfRatifyError,
    RatificationStatus,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.trust.features import grant_ratification
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)
_RATIFICATION_ID = UUID("01910000-0000-7000-8000-00000000f001")
_TARGET_REF = UUID("01910000-0000-7000-8000-00000000f002")
_REQUESTER_ID = UUID("01910000-0000-7000-8000-00000000f003")
_OTHER_PRINCIPAL_ID = UUID("01910000-0000-7000-8000-00000000f004")
_CORRELATION_ID = UUID("01910000-0000-7000-8000-0000000000aa")
_GENESIS_EVENT_ID = UUID("01910000-0000-7000-8000-00000000f101")
_TRANSITION_EVENT_ID = UUID("01910000-0000-7000-8000-00000000f102")
_COMMAND_NAME = "AbortRun"
_CONSEQUENCE_CLASS = "first_of_kind"


async def _seed_requested(store: InMemoryEventStore, *, requested_by: UUID = _REQUESTER_ID) -> None:
    """Append a RatificationRequested so the Ratification is in Requested status."""
    event = RatificationRequested(
        ratification_id=_RATIFICATION_ID,
        target_action_id=_TARGET_REF,
        command_name=_COMMAND_NAME,
        consequence_class=_CONSEQUENCE_CLASS,
        requested_by=requested_by,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Ratification",
        stream_id=_RATIFICATION_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=_GENESIS_EVENT_ID,
                command_name="RequestRatification",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=requested_by,
            )
        ],
    )


@pytest.mark.unit
async def test_grant_ratification_handler_appends_granted_by_independent_principal() -> None:
    store = InMemoryEventStore()
    await _seed_requested(store)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = grant_ratification.bind(deps)

    returned = await handler(
        grant_ratification.GrantRatification(ratification_id=_RATIFICATION_ID),
        principal_id=_OTHER_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned is None

    events, _ = await store.load("Ratification", _RATIFICATION_ID)
    assert events[-1].event_type == "RatificationGranted"
    folded = fold([from_stored(s) for s in events])
    assert folded is not None
    assert folded.status == RatificationStatus.GRANTED


@pytest.mark.unit
async def test_grant_ratification_handler_raises_self_sign_when_requester_grants() -> None:
    """Independence end-to-end: the envelope principal becomes granted_by, so a
    requester granting its own request raises RatificationRequesterCannotSelfRatifyError."""
    store = InMemoryEventStore()
    await _seed_requested(store, requested_by=_REQUESTER_ID)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = grant_ratification.bind(deps)

    with pytest.raises(RatificationRequesterCannotSelfRatifyError):
        await handler(
            grant_ratification.GrantRatification(ratification_id=_RATIFICATION_ID),
            principal_id=_REQUESTER_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_grant_ratification_handler_raises_not_found_when_absent() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store)
    handler = grant_ratification.bind(deps)

    with pytest.raises(RatificationNotFoundError):
        await handler(
            grant_ratification.GrantRatification(ratification_id=_RATIFICATION_ID),
            principal_id=_OTHER_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_grant_ratification_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_requested(store)
    deps = build_deps(ids=[_TRANSITION_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = grant_ratification.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            grant_ratification.GrantRatification(ratification_id=_RATIFICATION_ID),
            principal_id=_OTHER_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
