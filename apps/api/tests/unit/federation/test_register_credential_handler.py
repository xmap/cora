"""Application-handler tests for the `register_credential` slice.

Pins the cross-BC atomic write: every successful `register_credential`
call writes ONE `CredentialRegistered` event on the Credential stream
AND ONE `DecisionRegistered` audit event on the Decision stream via
`EventStore.append_streams`. Mirrors the `define_permit` precedent
(`PermitDefined` + `DecisionRegistered`) with distinct stream-id
semantics: register_credential mints a separate Decision id and
`choice` carries `str(credential_id)` for cross-stream correlation.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.credential import CredentialPurpose
from cora.federation.errors import UnauthorizedError
from cora.federation.features import register_credential
from cora.federation.features.register_credential import RegisterCredential
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_NEW_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed201")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed202")
_CREDENTIAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed203")
_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed204")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed299")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed2aa")
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/signing#v1"
_PUBLIC_REF = "vault://kv/cora/federation/aps-2bm/signing/pub#v1"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    # register_credential consumes 4 ids in order:
    #   1) new credential_id
    #   2) decision_id (the audit Decision's stream id)
    #   3) credential event_id (one CredentialRegistered event)
    #   4) decision event_id (one DecisionRegistered event)
    return _build_deps_shared(
        ids=[_NEW_CREDENTIAL_ID, _DECISION_ID, _CREDENTIAL_EVENT_ID, _DECISION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> RegisterCredential:
    base: dict[str, object] = {
        "facility_code": "aps-2bm",
        "audience": "peer.example.org",
        "purpose": CredentialPurpose.SIGNING,
        "secret_ref": _SECRET_REF,
        "public_material_ref": _PUBLIC_REF,
        "expires_at": _EXPIRES_AT,
    }
    base.update(overrides)
    return RegisterCredential(**base)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_register_credential_handler_returns_generated_credential_id() -> None:
    deps = _build_deps()
    handler = register_credential.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_CREDENTIAL_ID


@pytest.mark.unit
async def test_register_credential_handler_appends_to_credential_and_decision_streams() -> None:
    """Cross-BC atomic write: CredentialRegistered on Credential stream AND
    DecisionRegistered on Decision stream via append_streams."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    credential_events, credential_version = await store.load("Credential", _NEW_CREDENTIAL_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)

    assert credential_version == 1
    assert decision_version == 1
    assert len(credential_events) == 1
    assert len(decision_events) == 1
    assert credential_events[0].event_type == "CredentialRegistered"
    assert decision_events[0].event_type == "DecisionRegistered"


@pytest.mark.unit
async def test_register_credential_handler_writes_credential_payload_fields() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    credential_events, _ = await store.load("Credential", _NEW_CREDENTIAL_ID)
    payload = credential_events[0].payload
    assert payload["credential_id"] == str(_NEW_CREDENTIAL_ID)
    assert payload["facility_id"] == "aps-2bm"
    assert payload["audience"] == "peer.example.org"
    assert payload["purpose"] == CredentialPurpose.SIGNING.value
    assert payload["secret_ref"] == _SECRET_REF
    assert payload["public_material_ref"] == _PUBLIC_REF
    assert payload["expires_at"] == _EXPIRES_AT.isoformat()
    assert payload["registered_by"] == str(_PRINCIPAL_ID)
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_register_credential_handler_decision_audit_carries_actor_and_choice() -> None:
    """The co-written DecisionRegistered audit pins decided_by == principal_id,
    context == 'CredentialRegistered', and choice == str(new credential_id) for
    cross-stream correlation."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    payload = decision_events[0].payload
    assert payload["decision_id"] == str(_DECISION_ID)
    assert payload["decided_by"] == str(_PRINCIPAL_ID)
    assert payload["context"] == "CredentialRegistered"
    assert payload["choice"] == str(_NEW_CREDENTIAL_ID)
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_register_credential_handler_propagates_envelope_to_both_streams() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    credential_events, _ = await store.load("Credential", _NEW_CREDENTIAL_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    for events in (credential_events, decision_events):
        stored = events[0]
        assert stored.correlation_id == _CORRELATION_ID
        assert stored.causation_id is None


@pytest.mark.unit
async def test_register_credential_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = register_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_register_credential_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on either stream."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    credential_events, credential_version = await store.load("Credential", _NEW_CREDENTIAL_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)
    assert credential_version == 0
    assert decision_version == 0
    assert credential_events == []
    assert decision_events == []
