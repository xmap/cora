"""Application-handler unit tests for the `request_ratification` slice (genesis).

Pure-decider behavior is exercised in `ratification/test_request_ratification_decider.py`
and the sibling PBT; here we pin the handler-level concerns: caller-supplied-id
return, event-store append + envelope shape, and the authz-deny path.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.trust import UnauthorizedError
from cora.trust.aggregates.ratification import (
    RatificationStatus,
    fold,
    from_stored,
)
from cora.trust.features import request_ratification
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)
_RATIFICATION_ID = UUID("01910000-0000-7000-8000-00000000f001")
_TARGET_REF = UUID("01910000-0000-7000-8000-00000000f002")
_PRINCIPAL_ID = UUID("01910000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01910000-0000-7000-8000-0000000000aa")
_GENESIS_EVENT_ID = UUID("01910000-0000-7000-8000-00000000f101")
_COMMAND_NAME = "AbortRun"
_CONSEQUENCE_CLASS = "first_of_kind"


def _request_command() -> request_ratification.RequestRatification:
    return request_ratification.RequestRatification(
        ratification_id=_RATIFICATION_ID,
        target_action_id=_TARGET_REF,
        command_name=_COMMAND_NAME,
        consequence_class=_CONSEQUENCE_CLASS,
    )


@pytest.mark.unit
async def test_request_ratification_handler_returns_caller_supplied_id() -> None:
    """Genesis: caller supplies ratification_id; handler returns it unchanged."""
    deps = build_deps(ids=[_GENESIS_EVENT_ID], now=_NOW)
    handler = request_ratification.bind(deps)

    returned = await handler(
        _request_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned == _RATIFICATION_ID


@pytest.mark.unit
async def test_request_ratification_handler_appends_ratification_requested_to_store() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_GENESIS_EVENT_ID], now=_NOW, event_store=store)
    handler = request_ratification.bind(deps)

    await handler(
        _request_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Ratification", _RATIFICATION_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RatificationRequested"
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.principal_id == _PRINCIPAL_ID
    assert stored.metadata == {"command": "RequestRatification"}
    folded = fold([from_stored(s) for s in events])
    assert folded is not None
    assert folded.status == RatificationStatus.REQUESTED
    assert folded.requested_by == _PRINCIPAL_ID


@pytest.mark.unit
async def test_request_ratification_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_GENESIS_EVENT_ID], now=_NOW, deny=True)
    handler = request_ratification.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _request_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
