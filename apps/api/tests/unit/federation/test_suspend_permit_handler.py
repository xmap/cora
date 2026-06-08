"""Application-handler tests for the `suspend_permit` slice.

Covers the authz denial path (no event written), strict-not-idempotent
posture on re-suspend, FSM precondition rejection on Defined / Revoked,
not-found on an unknown permit, and the success path's event envelope
shape (correlation_id, causation_id, and the suspended_by
denorm on payload).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    PermitCannotSuspendError,
    PermitDefined,
    PermitNotFoundError,
    PermitRevoked,
    ReadScope,
    ScopeRef,
    event_type_name,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import suspend_permit
from cora.federation.features.suspend_permit import SuspendPermit
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import (
    seed_active_permit,
    seed_defined_permit,
    seed_suspended_permit,
)

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed003")
_SUSPEND_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed004")
_REVOKE_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed005")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed006")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEXT_EVENT_ID],
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_suspend_permit_handler_appends_event_to_active_permit() -> None:
    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = suspend_permit.bind(deps)
    await handler(
        SuspendPermit(permit_id=_PERMIT_ID, reason="peer paused outbound"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Permit", _PERMIT_ID)
    assert version == 3
    stored = events[-1]
    assert stored.event_type == "PermitSuspended"
    assert stored.payload["suspended_by"] == str(_PRINCIPAL_ID)
    assert stored.payload["permit_id"] == str(_PERMIT_ID)
    assert stored.payload["reason"] == "peer paused outbound"
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None


@pytest.mark.unit
async def test_suspend_permit_handler_event_payload_carries_reason() -> None:
    """`reason` flows from the command through the decider onto the
    emitted `PermitSuspended` event payload (audit context survives
    on the immutable event log)."""
    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = suspend_permit.bind(deps)
    await handler(
        SuspendPermit(permit_id=_PERMIT_ID, reason="peer paused outbound"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Permit", _PERMIT_ID)
    assert events[-1].payload["reason"] == "peer paused outbound"


@pytest.mark.unit
async def test_suspend_permit_handler_event_payload_records_none_reason() -> None:
    """When the operator omits `reason`, the emitted event carries
    None on the payload (round-trip stays clean)."""
    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = suspend_permit.bind(deps)
    await handler(
        SuspendPermit(permit_id=_PERMIT_ID, reason=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Permit", _PERMIT_ID)
    assert events[-1].payload["reason"] is None


@pytest.mark.unit
async def test_suspend_permit_handler_raises_not_found_for_unknown_permit() -> None:
    deps = _build_deps()
    handler = suspend_permit.bind(deps)
    with pytest.raises(PermitNotFoundError):
        await handler(
            SuspendPermit(permit_id=_PERMIT_ID, reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_suspend_permit_handler_raises_cannot_suspend_when_defined() -> None:
    """A Defined permit must be Activated first; suspend rejects."""
    store = InMemoryEventStore()
    await seed_defined_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = suspend_permit.bind(deps)
    with pytest.raises(PermitCannotSuspendError):
        await handler(
            SuspendPermit(permit_id=_PERMIT_ID, reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_suspend_permit_handler_strict_not_idempotent_on_re_suspend() -> None:
    """Re-suspending a Suspended permit MUST raise rather than no-op."""
    store = InMemoryEventStore()
    await seed_suspended_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        suspend_event_id=_SUSPEND_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        suspended_at=_T2,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = suspend_permit.bind(deps)
    with pytest.raises(PermitCannotSuspendError):
        await handler(
            SuspendPermit(permit_id=_PERMIT_ID, reason="re-suspend"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 3  # untouched after re-suspend rejection


@pytest.mark.unit
async def test_suspend_permit_handler_raises_cannot_suspend_when_revoked() -> None:
    """Revoked is terminal; suspend rejects."""
    store = InMemoryEventStore()
    # Seed Defined -> Activated -> Revoked inline (no shared helper for revoked).
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    revoked = PermitRevoked(
        permit_id=_PERMIT_ID,
        revoked_by=_PRINCIPAL_ID,
        occurred_at=_T2,
    )
    await store.append(
        stream_type="Permit",
        stream_id=_PERMIT_ID,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(revoked),
                payload=to_payload(revoked),
                occurred_at=revoked.occurred_at,
                event_id=_REVOKE_EVENT_ID,
                command_name="RevokePermit",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = suspend_permit.bind(deps)
    with pytest.raises(PermitCannotSuspendError):
        await handler(
            SuspendPermit(permit_id=_PERMIT_ID, reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_suspend_permit_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = suspend_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            SuspendPermit(permit_id=_PERMIT_ID, reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_suspend_permit_handler_denied_does_not_write_to_stream() -> None:
    """Authz-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = suspend_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            SuspendPermit(permit_id=_PERMIT_ID, reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 2  # untouched after Defined + Activated seed


@pytest.mark.unit
async def test_suspend_permit_handler_records_principal_as_suspended_by() -> None:
    """The handler injects the request envelope's `principal_id` as
    `suspended_by` on the emitted event (audit anchor for the
    operator gesture)."""
    other_actor_id = ActorId(UUID("01900000-0000-7000-8000-000000aa0001"))
    store = InMemoryEventStore()
    # Seed an Active permit defined BY a different actor; the suspender
    # should still be recorded as the invoking principal.
    genesis = PermitDefined(
        permit_id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({UUID("01900000-0000-7000-8000-00000000c001")}),
        allowed_payload_types=frozenset({"application/vnd.cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=other_actor_id,
        terms=OutboundTerms(
            scopes=frozenset({ScopeRef(kind="dataset", name="alpha")}),
            read_scope=ReadScope.READ_ALL_ARTIFACTS,
            onward_action_scope=OnwardActionScope.READ_ONLY,
        ),
        occurred_at=_T0,
    )
    await store.append(
        stream_type="Permit",
        stream_id=_PERMIT_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_GENESIS_EVENT_ID,
                command_name="DefinePermit",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=other_actor_id,
            )
        ],
    )
    from cora.federation.aggregates.permit import PermitActivated

    activated = PermitActivated(
        permit_id=_PERMIT_ID,
        activated_by=other_actor_id,
        occurred_at=_T1,
    )
    await store.append(
        stream_type="Permit",
        stream_id=_PERMIT_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(activated),
                payload=to_payload(activated),
                occurred_at=activated.occurred_at,
                event_id=_ACTIVATE_EVENT_ID,
                command_name="ActivatePermit",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=other_actor_id,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = suspend_permit.bind(deps)
    await handler(
        SuspendPermit(permit_id=_PERMIT_ID, reason=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Permit", _PERMIT_ID)
    assert events[-1].payload["suspended_by"] == str(_PRINCIPAL_ID)
