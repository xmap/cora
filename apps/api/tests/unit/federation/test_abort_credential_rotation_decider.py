"""Unit tests for the `abort_credential_rotation` slice's pure decider.

Pin the FSM source-state guard (Rotating is the only legal source),
the not-found branch, idempotency (same inputs -> same outputs),
handler-injected `rotation_aborted_by` reproducibility,
and the strict-not-idempotent posture (re-aborting an Active
credential raises rather than no-ops).

`reason` flows from the command through the decider onto the emitted
`CredentialRotationAborted` event payload so operator context
survives on the immutable event log; tests pin both the
with-reason and the None-default paths.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialRotationAborted,
    CredentialStatus,
)
from cora.federation.features import abort_credential_rotation
from cora.federation.features.abort_credential_rotation import (
    AbortCredentialRotation,
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


def _command(**overrides: object) -> AbortCredentialRotation:
    base: dict[str, object] = {
        "credential_id": _CREDENTIAL_ID,
        "aborted_by": _PRINCIPAL_ID,
        "reason": "peer refused new material",
    }
    base.update(overrides)
    return AbortCredentialRotation(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_abort_credential_rotation_emits_event_when_state_is_rotating() -> None:
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
        pending_public_material_ref="vault://pending/pub/v2",
    )
    events = abort_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_aborted_by=_PRINCIPAL_ID,
    )
    assert events == [
        CredentialRotationAborted(
            credential_id=_CREDENTIAL_ID,
            rotation_aborted_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
            reason="peer refused new material",
        )
    ]


@pytest.mark.unit
def test_abort_credential_rotation_rejects_when_state_is_none() -> None:
    """The credential must exist; missing state raises CredentialNotFoundError."""
    with pytest.raises(CredentialNotFoundError):
        abort_credential_rotation.decide(
            state=None,
            command=_command(),
            now=_NOW,
            rotation_aborted_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_abort_credential_rotation_rejects_when_state_is_active() -> None:
    """An Active credential has no rotation in flight; abort rejects."""
    state = _credential(CredentialStatus.ACTIVE)
    with pytest.raises(CredentialCannotRotateError) as exc:
        abort_credential_rotation.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotation_aborted_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "abort_rotation"
    assert exc.value.current_status is CredentialStatus.ACTIVE


@pytest.mark.unit
def test_abort_credential_rotation_rejects_when_state_is_revoked() -> None:
    """Revoked is terminal; abort rejects."""
    state = _credential(CredentialStatus.REVOKED)
    with pytest.raises(CredentialCannotRotateError) as exc:
        abort_credential_rotation.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotation_aborted_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "abort_rotation"
    assert exc.value.current_status is CredentialStatus.REVOKED


@pytest.mark.unit
def test_abort_credential_rotation_flows_reason_onto_event_payload() -> None:
    """`reason` is captured on the command and flows through to the
    emitted `CredentialRotationAborted` event so operator context
    survives on the immutable event log."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    events = abort_credential_rotation.decide(
        state=state,
        command=_command(reason="SecretStore generation failed mid-flight"),
        now=_NOW,
        rotation_aborted_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CredentialRotationAborted)
    assert event.reason == "SecretStore generation failed mid-flight"


@pytest.mark.unit
def test_abort_credential_rotation_defaults_reason_to_none_when_omitted() -> None:
    """`reason` defaults to None on the command and the emitted event
    carries None when the operator did not supply one."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    events = abort_credential_rotation.decide(
        state=state,
        command=AbortCredentialRotation(
            credential_id=_CREDENTIAL_ID,
            aborted_by=_PRINCIPAL_ID,
        ),
        now=_NOW,
        rotation_aborted_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CredentialRotationAborted)
    assert event.reason is None
    assert event.rotation_aborted_by == _PRINCIPAL_ID


@pytest.mark.unit
def test_abort_credential_rotation_is_pure_same_inputs_same_outputs() -> None:
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    first = abort_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_aborted_by=_PRINCIPAL_ID,
    )
    second = abort_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_aborted_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_abort_credential_rotation_uses_handler_injected_actor_id_verbatim() -> None:
    """Sanity: handler-injected `rotation_aborted_by` is used
    verbatim; decider doesn't synthesize it."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    injected = uuid4()
    events = abort_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_aborted_by=injected,
    )
    assert events[0].rotation_aborted_by == injected


@pytest.mark.unit
def test_abort_credential_rotation_uses_handler_injected_now_verbatim() -> None:
    """`now` is injected from the handler's clock per the
    non-determinism principle; the decider records it verbatim."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = abort_credential_rotation.decide(
        state=state,
        command=_command(),
        now=custom_now,
        rotation_aborted_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_abort_credential_rotation_actor_id_independent_of_registered_by() -> None:
    """The aborting actor need NOT be the credential's genesis-registering
    actor; the emitted event records whichever id the handler injects."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    events = abort_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_aborted_by=_OTHER_ACTOR_ID,
    )
    assert events[0].rotation_aborted_by == _OTHER_ACTOR_ID
    assert state.registered_by == _REGISTERED_BY


@pytest.mark.unit
def test_abort_credential_rotation_does_not_mint_new_id() -> None:
    """Transitions reuse the aggregate id from state; only genesis mints."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
    )
    events = abort_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_aborted_by=_PRINCIPAL_ID,
    )
    assert events[0].credential_id == state.id
