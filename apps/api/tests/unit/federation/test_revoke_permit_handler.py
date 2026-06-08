"""Application-handler tests for the `revoke_permit` slice.

Covers authz denial, FSM not-found rejection, strict-not-idempotent
re-revoke rejection, and the event-envelope shape (correlation_id +
causation_id propagation, `revoked_by` denorm carried from
`principal_id`).
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
    PermitCannotRevokeError,
    PermitDefined,
    PermitNotFoundError,
    PermitSuspended,
    ReadScope,
    ScopeRef,
    event_type_name,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import revoke_permit
from cora.federation.features.revoke_permit import RevokePermit
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed011")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed012")
_ACTIVATED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed013")
_SUSPENDED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed014")
_REVOKED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed015")
_FOLLOWUP_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed016")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_DEFINED_BY_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000009a"))
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_EXPIRES_AT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000000bb1")


def _outbound_terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="public", qualifier=None)}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


async def _append(
    store: InMemoryEventStore,
    event: PermitDefined | PermitActivated | PermitSuspended,
    *,
    event_id: UUID,
    command_name: str,
    expected_version: int,
) -> None:
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=event_id,
        command_name=command_name,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Permit",
        stream_id=_PERMIT_ID,
        expected_version=expected_version,
        events=[new_event],
    )


async def _seed_defined_permit(store: InMemoryEventStore) -> None:
    genesis = PermitDefined(
        permit_id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({_CREDENTIAL_ID}),
        allowed_payload_types=frozenset({"application/json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        defined_by=_DEFINED_BY_ACTOR_ID,
        terms=_outbound_terms(),
        occurred_at=_T0,
    )
    await _append(
        store,
        genesis,
        event_id=_DEFINED_EVENT_ID,
        command_name="DefinePermit",
        expected_version=0,
    )


async def _seed_active_permit(store: InMemoryEventStore) -> None:
    await _seed_defined_permit(store)
    activated = PermitActivated(
        permit_id=_PERMIT_ID,
        activated_by=_PRINCIPAL_ID,
        occurred_at=_T1,
    )
    await _append(
        store,
        activated,
        event_id=_ACTIVATED_EVENT_ID,
        command_name="ActivatePermit",
        expected_version=1,
    )


async def _seed_suspended_permit(store: InMemoryEventStore) -> None:
    await _seed_active_permit(store)
    suspended = PermitSuspended(
        permit_id=_PERMIT_ID,
        suspended_by=_PRINCIPAL_ID,
        occurred_at=_T1,
    )
    await _append(
        store,
        suspended,
        event_id=_SUSPENDED_EVENT_ID,
        command_name="SuspendPermit",
        expected_version=2,
    )


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> Kernel:
    return _build_deps_shared(
        ids=ids if ids is not None else [_REVOKED_EVENT_ID],
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_revoke_permit_handler_appends_event_from_defined() -> None:
    store = InMemoryEventStore()
    await _seed_defined_permit(store)
    deps = _build_deps(event_store=store)
    handler = revoke_permit.bind(deps)

    await handler(
        RevokePermit(permit_id=_PERMIT_ID, reason="peer decommissioned"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Permit", _PERMIT_ID)
    assert version == 2
    transition = events[-1]
    assert transition.event_type == "PermitRevoked"
    assert transition.payload["permit_id"] == str(_PERMIT_ID)
    assert transition.payload["revoked_by"] == str(_PRINCIPAL_ID)
    assert transition.payload["reason"] == "peer decommissioned"
    assert transition.correlation_id == _CORRELATION_ID
    assert transition.causation_id is None


@pytest.mark.unit
async def test_revoke_permit_handler_event_payload_records_none_reason() -> None:
    """When the operator omits `reason`, the emitted event carries
    None on the payload (round-trip stays clean)."""
    store = InMemoryEventStore()
    await _seed_defined_permit(store)
    deps = _build_deps(event_store=store)
    handler = revoke_permit.bind(deps)

    await handler(
        RevokePermit(permit_id=_PERMIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Permit", _PERMIT_ID)
    assert events[-1].payload["reason"] is None


@pytest.mark.unit
async def test_revoke_permit_handler_appends_event_from_active() -> None:
    store = InMemoryEventStore()
    await _seed_active_permit(store)
    deps = _build_deps(event_store=store)
    handler = revoke_permit.bind(deps)

    await handler(
        RevokePermit(permit_id=_PERMIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 3


@pytest.mark.unit
async def test_revoke_permit_handler_appends_event_from_suspended() -> None:
    store = InMemoryEventStore()
    await _seed_suspended_permit(store)
    deps = _build_deps(event_store=store)
    handler = revoke_permit.bind(deps)

    await handler(
        RevokePermit(permit_id=_PERMIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 4


@pytest.mark.unit
async def test_revoke_permit_handler_propagates_causation_id() -> None:
    store = InMemoryEventStore()
    await _seed_defined_permit(store)
    deps = _build_deps(event_store=store)
    handler = revoke_permit.bind(deps)

    causation_id = UUID("01900000-0000-7000-8000-0000000000cc")
    await handler(
        RevokePermit(permit_id=_PERMIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation_id,
    )

    events, _ = await store.load("Permit", _PERMIT_ID)
    assert events[-1].causation_id == causation_id


@pytest.mark.unit
async def test_revoke_permit_handler_raises_not_found_for_unknown_permit() -> None:
    deps = _build_deps(event_store=InMemoryEventStore())
    handler = revoke_permit.bind(deps)
    with pytest.raises(PermitNotFoundError):
        await handler(
            RevokePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_revoke_permit_handler_raises_on_replay() -> None:
    """Second revoke on the same stream raises `PermitCannotRevokeError`."""
    store = InMemoryEventStore()
    await _seed_defined_permit(store)
    deps = _build_deps(event_store=store)
    handler = revoke_permit.bind(deps)
    await handler(
        RevokePermit(permit_id=_PERMIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps2 = _build_deps(event_store=store, ids=[_FOLLOWUP_EVENT_ID])
    handler2 = revoke_permit.bind(deps2)
    with pytest.raises(PermitCannotRevokeError):
        await handler2(
            RevokePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after = await store.load("Permit", _PERMIT_ID)
    assert version_after == 2  # only one PermitRevoked event was appended


@pytest.mark.unit
async def test_revoke_permit_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await _seed_defined_permit(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = revoke_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RevokePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_revoke_permit_handler_denied_does_not_write_to_stream() -> None:
    """Authorize-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    await _seed_defined_permit(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = revoke_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RevokePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Permit", _PERMIT_ID)
    assert version == 1  # untouched: just the PermitDefined seed
