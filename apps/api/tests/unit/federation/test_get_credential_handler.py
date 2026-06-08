"""Application-handler tests for `get_credential` query slice.

Pins the Path C composition: authorize -> load_credential ->
load_credential_timestamps -> CredentialView. With no pool wired
in unit test mode, timestamps fold to None and the handler still
returns a hydrated CredentialView. Mirrors the `get_calibration`
precedent.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.credential import (
    CredentialPurpose,
    CredentialRegistered,
    CredentialStatus,
    event_type_name,
    to_payload,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import get_credential
from cora.federation.features.get_credential import GetCredential
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed301")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed302")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed304"))
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/signing#v1"
_PUBLIC_REF = "vault://kv/cora/federation/aps-2bm/signing/pub#v1"


async def _seed(store: InMemoryEventStore) -> None:
    genesis = CredentialRegistered(
        credential_id=_CREDENTIAL_ID,
        facility_id="aps-2bm",
        audience="peer.example.org",
        purpose=CredentialPurpose.SIGNING,
        secret_ref=_SECRET_REF,
        public_material_ref=_PUBLIC_REF,
        expires_at=_EXPIRES_AT,
        registered_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(genesis),
        payload=to_payload(genesis),
        occurred_at=genesis.occurred_at,
        event_id=_GENESIS_EVENT_ID,
        command_name="RegisterCredential",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_ACTOR_ID,
    )
    await store.append(
        stream_type="Credential",
        stream_id=_CREDENTIAL_ID,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_credential_view_on_hit() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_credential.bind(deps)
    view = await handler(
        GetCredential(credential_id=_CREDENTIAL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.credential.id == _CREDENTIAL_ID
    assert view.credential.facility_id == "aps-2bm"
    assert view.credential.audience == "peer.example.org"
    assert view.credential.purpose == CredentialPurpose.SIGNING
    assert view.credential.secret_ref == _SECRET_REF
    assert view.credential.public_material_ref == _PUBLIC_REF
    assert view.credential.expires_at == _EXPIRES_AT
    assert view.credential.registered_by == _ACTOR_ID
    assert view.credential.status == CredentialStatus.ACTIVE
    assert view.credential.rotation_pending_secret_ref is None
    assert view.credential.rotation_pending_public_material_ref is None
    # No pool in this in-memory test, so projection-sourced timestamps
    # are absent. Pin the contract: handler returns CredentialView with
    # timestamps=None rather than failing.
    assert view.timestamps is None


@pytest.mark.unit
async def test_handler_returns_none_on_miss() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_credential.bind(deps)
    view = await handler(
        GetCredential(credential_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = get_credential.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetCredential(credential_id=_CREDENTIAL_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_load_when_denied() -> None:
    """An empty store + deny means load_credential never runs; the
    handler raises before reaching the read path."""
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = get_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetCredential(credential_id=_CREDENTIAL_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
