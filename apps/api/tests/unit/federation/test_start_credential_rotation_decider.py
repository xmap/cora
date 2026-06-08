"""Unit tests for the `start_credential_rotation` slice's pure decider.

Pin the FSM single-source guard (Active is the only legal source),
the not-found branch, ref-shape validation (empty/whitespace
`new_secret_ref`, ref equal to the credential's current
`secret_ref`), purity (same inputs -> same outputs), and the
handler-injected `rotation_started_by` / `now` capture per
the non-determinism principle (capture, don't recompute).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialRotationStarted,
    CredentialStatus,
    InvalidCredentialSecretRefError,
)
from cora.federation.features import start_credential_rotation
from cora.federation.features.start_credential_rotation import (
    StartCredentialRotation,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fec001")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fec002")
_OTHER_ACTOR_ID = UUID("01900000-0000-7000-8000-000000fec003")
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))
_CURRENT_SECRET_REF = "vault://current/v1"
_PENDING_SECRET_REF = "vault://pending/v2"
_PENDING_PUBLIC_REF = "vault://pending/pub/v2"


def _credential(
    status: CredentialStatus,
    *,
    secret_ref: str = _CURRENT_SECRET_REF,
    pending_secret_ref: str | None = None,
    pending_public_material_ref: str | None = None,
) -> Credential:
    return Credential(
        id=_CREDENTIAL_ID,
        facility_id="aps-2bm",
        audience="peer-acme",
        purpose=CredentialPurpose.SIGNING,
        secret_ref=secret_ref,
        public_material_ref="vault://current/pub/v1",
        expires_at=_EXPIRES_AT,
        registered_by=_REGISTERED_BY,
        registered_at=_NOW,
        rotation_pending_secret_ref=pending_secret_ref,
        rotation_pending_public_material_ref=pending_public_material_ref,
        status=status,
    )


def _command(
    *,
    new_secret_ref: str = _PENDING_SECRET_REF,
    new_public_material_ref: str | None = _PENDING_PUBLIC_REF,
) -> StartCredentialRotation:
    return StartCredentialRotation(
        credential_id=_CREDENTIAL_ID,
        new_secret_ref=new_secret_ref,
        new_public_material_ref=new_public_material_ref,
    )


@pytest.mark.unit
def test_start_credential_rotation_emits_event_when_state_is_active() -> None:
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert events == [
        CredentialRotationStarted(
            credential_id=_CREDENTIAL_ID,
            pending_secret_ref=_PENDING_SECRET_REF,
            pending_public_material_ref=_PENDING_PUBLIC_REF,
            rotation_started_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_start_credential_rotation_rejects_when_state_is_none() -> None:
    """The credential must exist; missing state raises CredentialNotFoundError."""
    with pytest.raises(CredentialNotFoundError):
        start_credential_rotation.decide(
            state=None,
            command=_command(),
            now=_NOW,
            rotation_started_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_start_credential_rotation_rejects_when_state_is_rotating() -> None:
    """Single-source: starting a rotation against a Rotating credential rejects."""
    state = _credential(
        CredentialStatus.ROTATING,
        pending_secret_ref="vault://pending/v2",
        pending_public_material_ref="vault://pending/pub/v2",
    )
    with pytest.raises(CredentialCannotRotateError) as exc:
        start_credential_rotation.decide(
            state=state,
            command=_command(new_secret_ref="vault://pending/v3"),
            now=_NOW,
            rotation_started_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "start_rotation"
    assert exc.value.current_status is CredentialStatus.ROTATING


@pytest.mark.unit
def test_start_credential_rotation_rejects_when_state_is_revoked() -> None:
    """Revoked is terminal; start_rotation rejects."""
    state = _credential(CredentialStatus.REVOKED)
    with pytest.raises(CredentialCannotRotateError) as exc:
        start_credential_rotation.decide(
            state=state,
            command=_command(),
            now=_NOW,
            rotation_started_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "start_rotation"
    assert exc.value.current_status is CredentialStatus.REVOKED


@pytest.mark.unit
def test_start_credential_rotation_rejects_empty_new_secret_ref() -> None:
    """`new_secret_ref` must be non-empty after trimming."""
    state = _credential(CredentialStatus.ACTIVE)
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        start_credential_rotation.decide(
            state=state,
            command=_command(new_secret_ref=""),
            now=_NOW,
            rotation_started_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "new_secret_ref"
    assert "new_secret_ref" in str(exc.value)


@pytest.mark.unit
def test_start_credential_rotation_rejects_whitespace_new_secret_ref() -> None:
    """Whitespace-only `new_secret_ref` is structurally empty after trim."""
    state = _credential(CredentialStatus.ACTIVE)
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        start_credential_rotation.decide(
            state=state,
            command=_command(new_secret_ref="   \t  "),
            now=_NOW,
            rotation_started_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "new_secret_ref"
    assert exc.value.value == "   \t  "


@pytest.mark.unit
def test_start_credential_rotation_trims_new_secret_ref_before_capture() -> None:
    """Decider trims surrounding whitespace before capturing the pending ref."""
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(new_secret_ref=f"  {_PENDING_SECRET_REF}  "),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].pending_secret_ref == _PENDING_SECRET_REF


@pytest.mark.unit
def test_start_credential_rotation_rejects_when_new_secret_ref_equals_current() -> None:
    """Supplying a `new_secret_ref` equal to the current `secret_ref` is rejected."""
    state = _credential(CredentialStatus.ACTIVE, secret_ref=_CURRENT_SECRET_REF)
    with pytest.raises(CredentialCannotRotateError) as exc:
        start_credential_rotation.decide(
            state=state,
            command=_command(new_secret_ref=_CURRENT_SECRET_REF),
            now=_NOW,
            rotation_started_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "start_rotation_same_ref"
    assert exc.value.current_status is CredentialStatus.ACTIVE


@pytest.mark.unit
def test_start_credential_rotation_rejects_when_trimmed_ref_equals_current() -> None:
    """The equality check applies AFTER trimming; whitespace padding does not bypass."""
    state = _credential(CredentialStatus.ACTIVE, secret_ref=_CURRENT_SECRET_REF)
    with pytest.raises(CredentialCannotRotateError) as exc:
        start_credential_rotation.decide(
            state=state,
            command=_command(new_secret_ref=f"  {_CURRENT_SECRET_REF}  "),
            now=_NOW,
            rotation_started_by=_PRINCIPAL_ID,
        )
    assert exc.value.attempted == "start_rotation_same_ref"


@pytest.mark.unit
def test_start_credential_rotation_normalises_empty_public_material_ref_to_none() -> None:
    """An empty-string `new_public_material_ref` collapses to None on the event."""
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(new_public_material_ref=""),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].pending_public_material_ref is None


@pytest.mark.unit
def test_start_credential_rotation_normalises_whitespace_public_material_ref_to_none() -> None:
    """Whitespace-only `new_public_material_ref` also collapses to None after trim."""
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(new_public_material_ref="   "),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert events[0].pending_public_material_ref is None


@pytest.mark.unit
def test_start_credential_rotation_accepts_none_public_material_ref() -> None:
    """`new_public_material_ref=None` is accepted; event carries None."""
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(new_public_material_ref=None),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert events[0].pending_public_material_ref is None


@pytest.mark.unit
def test_start_credential_rotation_trims_public_material_ref() -> None:
    """Surrounding whitespace on the public ref is trimmed before capture."""
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(new_public_material_ref=f"  {_PENDING_PUBLIC_REF}  "),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert events[0].pending_public_material_ref == _PENDING_PUBLIC_REF


@pytest.mark.unit
def test_start_credential_rotation_is_pure_same_inputs_same_outputs() -> None:
    state = _credential(CredentialStatus.ACTIVE)
    first = start_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    second = start_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_start_credential_rotation_uses_handler_injected_actor_id_verbatim() -> None:
    """The decider records the handler-injected actor id without synthesising."""
    state = _credential(CredentialStatus.ACTIVE)
    injected = uuid4()
    events = start_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_started_by=injected,
    )
    assert events[0].rotation_started_by == injected


@pytest.mark.unit
def test_start_credential_rotation_uses_handler_injected_now_verbatim() -> None:
    """`now` is injected from the handler's clock; decider records it verbatim."""
    state = _credential(CredentialStatus.ACTIVE)
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(),
        now=custom_now,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_start_credential_rotation_actor_id_independent_of_registered_by() -> None:
    """The starting actor need NOT be the credential's genesis-registering actor."""
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_started_by=_OTHER_ACTOR_ID,
    )
    assert events[0].rotation_started_by == _OTHER_ACTOR_ID
    assert state.registered_by == _REGISTERED_BY


@pytest.mark.unit
def test_start_credential_rotation_does_not_mint_new_id() -> None:
    """Transitions reuse the aggregate id from state; only genesis mints."""
    state = _credential(CredentialStatus.ACTIVE)
    events = start_credential_rotation.decide(
        state=state,
        command=_command(),
        now=_NOW,
        rotation_started_by=_PRINCIPAL_ID,
    )
    assert events[0].credential_id == state.id
