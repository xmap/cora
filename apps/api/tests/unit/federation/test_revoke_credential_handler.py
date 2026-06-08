"""Application-handler tests for the `revoke_credential` slice.

Pins the cross-BC atomic write: every successful `revoke_credential`
call writes ONE `CredentialRevoked` event on the Credential stream
AND ONE `DecisionRegistered` audit event on the Decision stream via
`EventStore.append_streams`. Mirrors the `register_credential`
genesis cross-BC pattern with one twist: the Credential stream's
expected version is the loaded version (not zero) because revoke is a
TERMINAL transition on an existing stream, while the Decision stream
is fresh (expected version zero).

Revoking a credential is a security-touching action (a compromised
secret being retired; an operator pulling a peer's verification
material): the Decision-BC audit emission gives the SOC a single
stream to scrub when reconstructing incident timelines, which is why
this slice is cross-BC where the rotation lifecycle slices are not.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.credential import (
    CredentialCannotRevokeError,
    CredentialNotFoundError,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import revoke_credential
from cora.federation.features.revoke_credential import RevokeCredential
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import (
    seed_active_credential,
    seed_revoked_credential,
    seed_rotating_credential,
)

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed201")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed202")
_ROTATION_STARTED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed203")
_REVOKE_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed204")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed205")
_CREDENTIAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed206")
_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed207")
_FOLLOWUP_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed208")
_FOLLOWUP_CREDENTIAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed209")
_FOLLOWUP_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed20a")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> Kernel:
    # revoke_credential consumes 3 ids per successful call:
    #   1) decision_id (fresh Decision stream id)
    #   2) credential event_id (one CredentialRevoked event)
    #   3) decision event_id (one DecisionRegistered event)
    return _build_deps_shared(
        ids=(ids if ids is not None else [_DECISION_ID, _CREDENTIAL_EVENT_ID, _DECISION_EVENT_ID]),
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


def _command(reason: str | None = None) -> RevokeCredential:
    return RevokeCredential(credential_id=_CREDENTIAL_ID, reason=reason)


@pytest.mark.unit
async def test_revoke_credential_handler_appends_event_from_active() -> None:
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Credential", _CREDENTIAL_ID)
    assert version == 2
    transition = events[-1]
    assert transition.event_type == "CredentialRevoked"
    assert transition.payload["credential_id"] == str(_CREDENTIAL_ID)
    assert transition.payload["revoked_by"] == str(_PRINCIPAL_ID)
    assert transition.correlation_id == _CORRELATION_ID
    assert transition.causation_id is None


@pytest.mark.unit
async def test_revoke_credential_handler_appends_event_from_rotating() -> None:
    store = InMemoryEventStore()
    await seed_rotating_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        rotation_started_event_id=_ROTATION_STARTED_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        rotation_started_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version = await store.load("Credential", _CREDENTIAL_ID)
    assert version == 3


@pytest.mark.unit
async def test_revoke_credential_handler_appends_to_both_credential_and_decision_streams() -> None:
    """Cross-BC atomic write: CredentialRevoked on Credential stream AND
    DecisionRegistered on Decision stream via append_streams."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    credential_events, credential_version = await store.load("Credential", _CREDENTIAL_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)

    assert credential_version == 2  # genesis + revoke
    assert decision_version == 1  # fresh Decision stream
    assert len(credential_events) == 2
    assert len(decision_events) == 1
    assert credential_events[-1].event_type == "CredentialRevoked"
    assert decision_events[0].event_type == "DecisionRegistered"


@pytest.mark.unit
async def test_revoke_credential_handler_decision_audit_carries_actor_and_choice() -> None:
    """The co-written DecisionRegistered audit pins decided_by == principal_id,
    context == 'CredentialRevoked', and choice == str(credential_id) for
    cross-stream correlation."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    payload = decision_events[0].payload
    assert payload["decision_id"] == str(_DECISION_ID)
    assert payload["decided_by"] == str(_PRINCIPAL_ID)
    assert payload["context"] == "CredentialRevoked"
    assert payload["choice"] == str(_CREDENTIAL_ID)
    assert payload["occurred_at"] == _T2.isoformat()


@pytest.mark.unit
async def test_revoke_credential_handler_propagates_envelope_to_both_streams() -> None:
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    credential_events, _ = await store.load("Credential", _CREDENTIAL_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    credential_revoke = credential_events[-1]
    decision_audit = decision_events[0]
    assert credential_revoke.correlation_id == _CORRELATION_ID
    assert credential_revoke.causation_id is None
    assert decision_audit.correlation_id == _CORRELATION_ID
    assert decision_audit.causation_id is None


@pytest.mark.unit
async def test_revoke_credential_handler_propagates_causation_id() -> None:
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)

    causation_id = UUID("01900000-0000-7000-8000-0000000000cc")
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation_id,
    )

    credential_events, _ = await store.load("Credential", _CREDENTIAL_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    assert credential_events[-1].causation_id == causation_id
    assert decision_events[0].causation_id == causation_id


@pytest.mark.unit
async def test_revoke_credential_handler_event_payload_carries_reason() -> None:
    """`reason` flows from the command through the decider onto the
    emitted `CredentialRevoked` event payload (audit context survives
    on the immutable event log)."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    await handler(
        _command(reason="compromised secret being retired"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["reason"] == "compromised secret being retired"


@pytest.mark.unit
async def test_revoke_credential_handler_event_payload_records_none_reason() -> None:
    """When the operator omits `reason`, the emitted event carries
    None on the payload (round-trip stays clean)."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    await handler(
        _command(reason=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["reason"] is None


@pytest.mark.unit
async def test_revoke_credential_handler_raises_not_found_for_unknown_credential() -> None:
    deps = _build_deps(event_store=InMemoryEventStore())
    handler = revoke_credential.bind(deps)
    with pytest.raises(CredentialNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_revoke_credential_handler_raises_cannot_revoke_when_already_revoked() -> None:
    """Strict-not-idempotent: re-revoking an already-Revoked credential raises."""
    store = InMemoryEventStore()
    await seed_revoked_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        revoke_event_id=_REVOKE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        revoked_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    with pytest.raises(CredentialCannotRevokeError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Credential", _CREDENTIAL_ID)
    assert version == 2  # untouched seed (Registered + Revoked)


@pytest.mark.unit
async def test_revoke_credential_handler_strict_not_idempotent_on_re_revoke() -> None:
    """After a successful revoke the credential is Revoked; re-revoking MUST
    raise rather than no-op and MUST NOT write to either stream."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_first = await store.load("Credential", _CREDENTIAL_ID)
    assert version_after_first == 2

    deps2 = _build_deps(
        event_store=store,
        ids=[
            _FOLLOWUP_DECISION_ID,
            _FOLLOWUP_CREDENTIAL_EVENT_ID,
            _FOLLOWUP_DECISION_EVENT_ID,
        ],
    )
    handler2 = revoke_credential.bind(deps2)
    with pytest.raises(CredentialCannotRevokeError):
        await handler2(
            _command(reason="duplicate operator gesture"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after_reject = await store.load("Credential", _CREDENTIAL_ID)
    assert version_after_reject == 2  # untouched after re-revoke rejection
    _, followup_decision_version = await store.load("Decision", _FOLLOWUP_DECISION_ID)
    assert followup_decision_version == 0  # no second Decision stream landed


@pytest.mark.unit
async def test_revoke_credential_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = revoke_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_revoke_credential_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on EITHER stream."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = revoke_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, credential_version = await store.load("Credential", _CREDENTIAL_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)
    assert credential_version == 1  # untouched: just the CredentialRegistered seed
    assert decision_version == 0
    assert decision_events == []


@pytest.mark.unit
async def test_revoke_credential_handler_records_principal_as_revoked_by() -> None:
    """The handler injects the request envelope's `principal_id` as
    `revoked_by` on the emitted event (audit anchor for the
    operator gesture), regardless of who registered the credential."""
    store = InMemoryEventStore()
    # Seed Registered BY a different actor; the revoker should still be
    # recorded as the invoking principal.
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = revoke_credential.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["revoked_by"] == str(_PRINCIPAL_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    assert decision_events[0].payload["decided_by"] == str(_PRINCIPAL_ID)
