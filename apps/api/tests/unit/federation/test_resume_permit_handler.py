"""Application-handler tests for the `resume_permit` slice.

Covers happy-path event-append + envelope propagation, the authz
denial path (deny + no-write-on-deny), and FSM precondition rejects
(not-found + cannot-resume-when-not-Suspended). Seeds the Permit
stream inline via `to_new_event` because the Federation BC does not
yet ship a `tests/unit/federation/_helpers.py` (sibling Permit
transition slices add seed_* fns when the second consumer arrives).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    PermitActivated,
    PermitCannotResumeError,
    PermitDefined,
    PermitNotFoundError,
    PermitSuspended,
    ReadScope,
    ScopeRef,
    event_type_name,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import resume_permit
from cora.federation.features.resume_permit import ResumePermit
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_DEFINED_AT = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_ACTIVATED_AT = datetime(2026, 5, 30, 10, 30, 0, tzinfo=UTC)
_SUSPENDED_AT = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed003")
_SUSPEND_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed004")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed005")

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_DEFINING_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-0000000000bb"))
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEXT_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _outbound_terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="ct-2bm")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


async def _seed_defined_permit(store: InMemoryEventStore) -> None:
    defined = PermitDefined(
        permit_id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset(),
        allowed_payload_types=frozenset({"application/cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_DEFINING_PRINCIPAL_ID,
        terms=_outbound_terms(),
        occurred_at=_DEFINED_AT,
    )
    await store.append(
        stream_type="Permit",
        stream_id=_PERMIT_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(defined),
                payload=to_payload(defined),
                occurred_at=_DEFINED_AT,
                event_id=_GENESIS_EVENT_ID,
                command_name="DefinePermit",
                correlation_id=_CORRELATION_ID,
                principal_id=_DEFINING_PRINCIPAL_ID,
            )
        ],
    )


async def _seed_active_permit(store: InMemoryEventStore) -> None:
    await _seed_defined_permit(store)
    activated = PermitActivated(
        permit_id=_PERMIT_ID,
        activated_by=_DEFINING_PRINCIPAL_ID,
        occurred_at=_ACTIVATED_AT,
    )
    await store.append(
        stream_type="Permit",
        stream_id=_PERMIT_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(activated),
                payload=to_payload(activated),
                occurred_at=_ACTIVATED_AT,
                event_id=_ACTIVATE_EVENT_ID,
                command_name="ActivatePermit",
                correlation_id=_CORRELATION_ID,
                principal_id=_DEFINING_PRINCIPAL_ID,
            )
        ],
    )


async def _seed_suspended_permit(store: InMemoryEventStore) -> None:
    await _seed_active_permit(store)
    suspended = PermitSuspended(
        permit_id=_PERMIT_ID,
        suspended_by=_DEFINING_PRINCIPAL_ID,
        occurred_at=_SUSPENDED_AT,
    )
    await store.append(
        stream_type="Permit",
        stream_id=_PERMIT_ID,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(suspended),
                payload=to_payload(suspended),
                occurred_at=_SUSPENDED_AT,
                event_id=_SUSPEND_EVENT_ID,
                command_name="SuspendPermit",
                correlation_id=_CORRELATION_ID,
                principal_id=_DEFINING_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_resume_permit_handler_appends_resumed_event() -> None:
    store = InMemoryEventStore()
    await _seed_suspended_permit(store)
    deps = _build_deps(event_store=store)
    handler = resume_permit.bind(deps)
    await handler(
        ResumePermit(permit_id=_PERMIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Permit", _PERMIT_ID)
    assert version == 4  # Defined + Activated + Suspended + Resumed
    stored = events[-1]
    assert stored.event_type == "PermitResumed"
    assert stored.payload["permit_id"] == str(_PERMIT_ID)
    assert stored.payload["resumed_by"] == str(_PRINCIPAL_ID)
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.principal_id == _PRINCIPAL_ID


@pytest.mark.unit
async def test_resume_permit_handler_raises_not_found_for_unknown_permit() -> None:
    deps = _build_deps()
    handler = resume_permit.bind(deps)
    with pytest.raises(PermitNotFoundError):
        await handler(
            ResumePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_resume_permit_handler_raises_cannot_resume_when_active() -> None:
    """Strict-not-idempotent: resuming an Active permit raises 409 source."""
    store = InMemoryEventStore()
    await _seed_active_permit(store)
    deps = _build_deps(event_store=store)
    handler = resume_permit.bind(deps)
    with pytest.raises(PermitCannotResumeError):
        await handler(
            ResumePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 2  # untouched (Defined + Activated)


@pytest.mark.unit
async def test_resume_permit_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await _seed_suspended_permit(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = resume_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ResumePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_resume_permit_handler_denied_does_not_write_to_stream() -> None:
    """Authz-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    await _seed_suspended_permit(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = resume_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ResumePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 3  # untouched (Defined + Activated + Suspended)
