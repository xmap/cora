"""Unit tests for the `revoke_credential` slice's pure decider.

Widest-source terminal transition: any non-Revoked status (Active or
Rotating) -> Revoked. Strict-not-idempotent: re-revoking an already-
Revoked credential raises `CredentialCannotRevokeError` per the
`revoke_permit` / `deregister_supply` precedent.

`revoked_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`CredentialRevoked` event as the audit denorm.

`reason` flows from the command through the decider onto the emitted
`CredentialRevoked` event payload so operator context survives on
the immutable event log; tests pin both the with-reason and the
None-default paths.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRevokeError,
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialRevoked,
    CredentialStatus,
)
from cora.federation.features import revoke_credential
from cora.federation.features.revoke_credential import RevokeCredential
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed101")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed102")
_OTHER_ACTOR_ID = UUID("01900000-0000-7000-8000-000000fed103")
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed199"))


def _credential(
    status: CredentialStatus,
    *,
    pending_secret_ref: str | None = None,
    pending_public_material_ref: str | None = None,
) -> Credential:
    return Credential(
        id=_CREDENTIAL_ID,
        facility_id="aps-2bm",
        audience="peer-acme",
        purpose=CredentialPurpose.SIGNING,
        secret_ref="vault://current/v1",
        public_material_ref="vault://current/pub/v1",
        expires_at=_EXPIRES_AT,
        registered_by=_REGISTERED_BY,
        registered_at=_NOW,
        rotation_pending_secret_ref=pending_secret_ref,
        rotation_pending_public_material_ref=pending_public_material_ref,
        status=status,
    )


def _command(reason: str | None = None) -> RevokeCredential:
    return RevokeCredential(credential_id=_CREDENTIAL_ID, reason=reason)


@pytest.mark.unit
@pytest.mark.parametrize(
    "current_status",
    [
        CredentialStatus.ACTIVE,
        CredentialStatus.ROTATING,
    ],
)
def test_revoke_credential_emits_event_from_any_non_revoked_status(
    current_status: CredentialStatus,
) -> None:
    state = (
        _credential(
            current_status,
            pending_secret_ref="vault://pending/v2",
            pending_public_material_ref="vault://pending/pub/v2",
        )
        if current_status is CredentialStatus.ROTATING
        else _credential(current_status)
    )
    events = revoke_credential.decide(
        state=state,
        command=_command(),
        now=_NOW,
        revoked_by=_PRINCIPAL_ID,
    )
    assert events == [
        CredentialRevoked(
            credential_id=_CREDENTIAL_ID,
            revoked_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
            reason=None,
        )
    ]


@pytest.mark.unit
def test_revoke_credential_rejects_when_already_revoked() -> None:
    """Strict-not-idempotent: re-revoking a Revoked credential raises."""
    state = _credential(CredentialStatus.REVOKED)
    with pytest.raises(CredentialCannotRevokeError) as exc_info:
        revoke_credential.decide(
            state=state,
            command=_command(),
            now=_NOW,
            revoked_by=_PRINCIPAL_ID,
        )
    assert exc_info.value.credential_id == _CREDENTIAL_ID


@pytest.mark.unit
def test_revoke_credential_rejects_when_state_is_none() -> None:
    """The credential must exist; missing state raises CredentialNotFoundError."""
    with pytest.raises(CredentialNotFoundError) as exc_info:
        revoke_credential.decide(
            state=None,
            command=_command(),
            now=_NOW,
            revoked_by=_PRINCIPAL_ID,
        )
    assert exc_info.value.credential_id == _CREDENTIAL_ID


@pytest.mark.unit
def test_revoke_credential_captures_handler_injected_revoked_by() -> None:
    """`revoked_by` is captured verbatim from the handler, not recomputed."""
    arbitrary_principal = uuid4()
    events = revoke_credential.decide(
        state=_credential(CredentialStatus.ACTIVE),
        command=_command(),
        now=_NOW,
        revoked_by=arbitrary_principal,
    )
    assert events[0].revoked_by == arbitrary_principal


@pytest.mark.unit
def test_revoke_credential_uses_supplied_now_for_occurred_at() -> None:
    """Non-determinism injected from handler per project_non_determinism_principle."""
    custom_now = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
    events = revoke_credential.decide(
        state=_credential(CredentialStatus.ACTIVE),
        command=_command(),
        now=custom_now,
        revoked_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_revoke_credential_is_pure_same_inputs_same_outputs() -> None:
    state = _credential(CredentialStatus.ACTIVE)
    command = _command()
    first = revoke_credential.decide(
        state=state, command=command, now=_NOW, revoked_by=_PRINCIPAL_ID
    )
    second = revoke_credential.decide(
        state=state, command=command, now=_NOW, revoked_by=_PRINCIPAL_ID
    )
    assert first == second


@pytest.mark.unit
def test_revoke_credential_flows_reason_onto_event_payload() -> None:
    """`reason` is captured on the command and flows through to the
    emitted `CredentialRevoked` event so operator context survives
    on the immutable event log."""
    events = revoke_credential.decide(
        state=_credential(CredentialStatus.ACTIVE),
        command=_command(reason="compromised secret being retired"),
        now=_NOW,
        revoked_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CredentialRevoked)
    assert event.reason == "compromised secret being retired"


@pytest.mark.unit
def test_revoke_credential_defaults_reason_to_none_when_omitted() -> None:
    """`reason` defaults to None on the command and the emitted event
    carries None when the operator did not supply one."""
    events = revoke_credential.decide(
        state=_credential(CredentialStatus.ACTIVE),
        command=_command(),
        now=_NOW,
        revoked_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CredentialRevoked)
    assert event.reason is None


@pytest.mark.unit
def test_revoke_credential_actor_id_independent_of_registered_by() -> None:
    """The revoking actor need NOT be the credential's genesis-registering
    actor; the emitted event records whichever id the handler injects."""
    events = revoke_credential.decide(
        state=_credential(CredentialStatus.ACTIVE),
        command=_command(),
        now=_NOW,
        revoked_by=_OTHER_ACTOR_ID,
    )
    assert events[0].revoked_by == _OTHER_ACTOR_ID


@pytest.mark.unit
def test_revoke_credential_does_not_mint_new_id() -> None:
    """Transitions reuse the aggregate id from state; only genesis mints."""
    state = _credential(CredentialStatus.ACTIVE)
    events = revoke_credential.decide(
        state=state,
        command=_command(),
        now=_NOW,
        revoked_by=_PRINCIPAL_ID,
    )
    assert events[0].credential_id == state.id
