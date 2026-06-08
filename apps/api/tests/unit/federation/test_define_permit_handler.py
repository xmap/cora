"""Application-handler tests for the `define_permit` slice.

Pins the cross-BC atomic write: every successful `define_permit`
call writes ONE `PermitDefined` event on the Permit stream AND ONE
`DecisionRegistered` audit event on the Decision stream via
`EventStore.append_streams`. Mirrors the `define_agent` precedent
(`AgentDefined` + `ActorRegisteredV2`) but with distinct
stream-id semantics: define_permit mints a separate Decision id
(the audit event lives on its own Decision stream keyed by a fresh
decision_id; `choice` carries str(permit_id) for cross-stream
correlation).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    ReadScope,
    ScopeRef,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import define_permit
from cora.federation.features.define_permit import DefinePermit
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)
_NEW_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed001")
_PERMIT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed003")
_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed004")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed005")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    # define_permit consumes 4 ids in order:
    #   1) new permit_id
    #   2) decision_id (the audit Decision's stream id)
    #   3) permit event_id (one PermitDefined event)
    #   4) decision event_id (one DecisionRegistered event)
    return _build_deps_shared(
        ids=[_NEW_PERMIT_ID, _DECISION_ID, _PERMIT_EVENT_ID, _DECISION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> DefinePermit:
    base: dict[str, object] = {
        "peer_facility_code": "aps-2bm",
        "direction": Direction.OUTBOUND,
        "allowed_credential_ids": frozenset({_CREDENTIAL_ID}),
        "allowed_payload_types": frozenset({"application/json"}),
        "allowed_artifact_kinds": frozenset({"dataset"}),
        "abi_tier_floor": AbiTier.STABLE,
        "expires_at": _EXPIRES_AT,
        "terms": OutboundTerms(
            scopes=frozenset({ScopeRef(kind="dataset", name="public", qualifier=None)}),
            read_scope=ReadScope.READ_ALL_ARTIFACTS,
            onward_action_scope=OnwardActionScope.READ_ONLY,
        ),
    }
    base.update(overrides)
    return DefinePermit(**base)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_define_permit_handler_returns_generated_permit_id() -> None:
    deps = _build_deps()
    handler = define_permit.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_PERMIT_ID


@pytest.mark.unit
async def test_define_permit_handler_appends_to_both_permit_and_decision_streams() -> None:
    """Cross-BC atomic write: PermitDefined on Permit stream AND
    DecisionRegistered on Decision stream via append_streams."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_permit.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    permit_events, permit_version = await store.load("Permit", _NEW_PERMIT_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)

    assert permit_version == 1
    assert decision_version == 1
    assert len(permit_events) == 1
    assert len(decision_events) == 1
    assert permit_events[0].event_type == "PermitDefined"
    assert decision_events[0].event_type == "DecisionRegistered"


@pytest.mark.unit
async def test_define_permit_handler_writes_permit_payload_fields() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_permit.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    permit_events, _ = await store.load("Permit", _NEW_PERMIT_ID)
    payload = permit_events[0].payload
    assert payload["permit_id"] == str(_NEW_PERMIT_ID)
    assert payload["peer_facility_id"] == "aps-2bm"
    assert payload["direction"] == Direction.OUTBOUND.value
    assert payload["allowed_credential_ids"] == [str(_CREDENTIAL_ID)]
    assert payload["allowed_payload_types"] == ["application/json"]
    assert payload["allowed_artifact_kinds"] == ["dataset"]
    assert payload["abi_tier_floor"] == AbiTier.STABLE.value
    assert payload["defined_by"] == str(_PRINCIPAL_ID)
    assert payload["terms"]["kind"] == "Outbound"


@pytest.mark.unit
async def test_define_permit_handler_decision_audit_carries_actor_and_permit_id_choice() -> None:
    """The co-written DecisionRegistered audit pins decided_by == principal_id,
    context == 'PermitDefined', and choice == str(new permit_id) for
    cross-stream correlation."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_permit.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    payload = decision_events[0].payload
    assert payload["decision_id"] == str(_DECISION_ID)
    assert payload["decided_by"] == str(_PRINCIPAL_ID)
    assert payload["context"] == "PermitDefined"
    assert payload["choice"] == str(_NEW_PERMIT_ID)
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_define_permit_handler_propagates_envelope_to_both_streams() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_permit.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    permit_events, _ = await store.load("Permit", _NEW_PERMIT_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    for events in (permit_events, decision_events):
        stored = events[0]
        assert stored.correlation_id == _CORRELATION_ID
        assert stored.causation_id is None


@pytest.mark.unit
async def test_define_permit_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = define_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_define_permit_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on either stream."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    permit_events, permit_version = await store.load("Permit", _NEW_PERMIT_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)
    assert permit_version == 0
    assert decision_version == 0
    assert permit_events == []
    assert decision_events == []
