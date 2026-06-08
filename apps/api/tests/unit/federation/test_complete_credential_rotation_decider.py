"""Unit tests for the `complete_credential_rotation` slice's pure decider.

Pin the FSM source-state guard (Rotating is the only legal source),
the not-found branch, the belt-and-braces pending-ref-present guard,
purity (same inputs same outputs), and handler-injected
`rotation_completed_by` + `now` reproducibility.

`CompleteCredentialRotation` carries no operator-facing body fields
(no `reason`): the command is identity-only on the credential, and
the emitted `CredentialRotationCompleted` payload is identity-only
plus the actor / occurred_at audit anchors.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialRotationCompleted,
    CredentialStatus,
)
from cora.federation.features import complete_credential_rotation
from cora.federation.features.complete_credential_rotation import (
    CompleteCredentialRotation,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fec001")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fec002")
_OTHER_ACTOR_ID = UUID("01900000-0000-7000-8000-000000fec003")
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))


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


def _command() -> CompleteCredentialRotation:
    return CompleteCredentialRotation(credential_id=_CREDENTIAL_ID)


@pytest.mark.unit
def test_complete_credential_rotation_emits_event_when_state_is_rotating() -> None:
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
        pending_public_material_ref="vault://pending/pub/v2",
    )
    events = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_completed_by=_PRINCIPAL_ID,
    )
    assert events == [
        CredentialRotationCompleted(
            credential_id=_CREDENTIAL_ID,
            rotation_completed_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_complete_credential_rotation_rejects_when_state_is_none() -> None:
    """The credential must exist; missing state raises CredentialNotFoundError."""
    with pytest.raises(CredentialNotFoundError):
        complete_credential_rotation.decide(
            state=None,
            command=_command(),
            now=_NOW,
            rotation_completed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_complete_credential_rotation_rejects_when_state_is_active() -> None:
    """An Active credential has no rotation in flight; complete rejects."""
    state = _credential(CredentialStatus.ACTIVE)
    with pytest.raises(CredentialCannotRotateError) as exc:
        complete_credential_rotation.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotation_completed_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "complete_rotation"
    assert exc.value.current_status is CredentialStatus.ACTIVE


@pytest.mark.unit
def test_complete_credential_rotation_rejects_when_state_is_revoked() -> None:
    """Revoked is terminal; complete rejects."""
    state = _credential(CredentialStatus.REVOKED)
    with pytest.raises(CredentialCannotRotateError) as exc:
        complete_credential_rotation.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotation_completed_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "complete_rotation"
    assert exc.value.current_status is CredentialStatus.REVOKED


@pytest.mark.unit
def test_complete_credential_rotation_rejects_when_pending_secret_ref_is_none() -> None:
    """Belt-and-braces invariant: a Rotating credential with `None` pending
    secret ref signals a malformed event log; decider rejects locally
    rather than silently promoting `None` to current."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref=None,
        pending_public_material_ref="vault://pending/pub/v2",
    )
    with pytest.raises(CredentialCannotRotateError) as exc:
        complete_credential_rotation.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotation_completed_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "complete_rotation"


@pytest.mark.unit
def test_complete_credential_rotation_is_pure_same_inputs_same_outputs() -> None:
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
        pending_public_material_ref="vault://pending/pub/v2",
    )
    first = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_completed_by=_PRINCIPAL_ID,
    )
    second = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_completed_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_complete_credential_rotation_uses_handler_injected_actor_id_verbatim() -> None:
    """Sanity: handler-injected `rotation_completed_by` is used
    verbatim; decider doesn't synthesize it."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    injected = uuid4()
    events = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_completed_by=injected,
    )
    assert events[0].rotation_completed_by == injected


@pytest.mark.unit
def test_complete_credential_rotation_uses_handler_injected_now_verbatim() -> None:
    """`now` is injected from the handler's clock per the non-determinism
    principle; the decider records it verbatim."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=custom_now,
        rotation_completed_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_complete_credential_rotation_actor_id_independent_of_registered_by() -> None:
    """The completing actor need NOT be the credential's genesis-registering
    actor; the emitted event records whichever id the handler injects."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    events = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_completed_by=_OTHER_ACTOR_ID,
    )
    assert events[0].rotation_completed_by == _OTHER_ACTOR_ID
    assert state.registered_by == _REGISTERED_BY


@pytest.mark.unit
def test_complete_credential_rotation_does_not_mint_new_id() -> None:
    """Transitions reuse the aggregate id from state; only genesis mints."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    events = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_completed_by=_PRINCIPAL_ID,
    )
    assert events[0].credential_id == state.id


@pytest.mark.unit
def test_complete_credential_rotation_emits_identity_only_payload() -> None:
    """`CredentialRotationCompleted` carries only the three audit fields
    (credential_id, rotation_completed_by, occurred_at); the
    pending refs are not stamped on the event payload."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
        pending_public_material_ref="vault://pending/pub/v2",
    )
    events = complete_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_completed_by=_PRINCIPAL_ID,
    )
    event = events[0]
    assert isinstance(event, CredentialRotationCompleted)
    assert not hasattr(event, "pending_secret_ref")
    assert not hasattr(event, "pending_public_material_ref")
    assert not hasattr(event, "secret_ref")
