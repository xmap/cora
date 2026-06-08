"""Unit tests for the `register_credential` slice's pure decider.

Pin the genesis-collision guard, every field-shape rejection branch
(facility_id / audience / secret_ref empty + whitespace),
trimming-before-capture for those three fields, the optional
expires_at strict-future guard, the six purpose enum arms, purity
(same inputs -> same outputs), and handler-injected new_id /
registered_by / now capture per the non-determinism
principle (capture, don't recompute).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.credential import (
    Credential,
    CredentialAlreadyExistsError,
    CredentialExpiredError,
    CredentialPurpose,
    CredentialStatus,
    InvalidCredentialSecretRefError,
)
from cora.federation.features import register_credential
from cora.federation.features.register_credential import RegisterCredential
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed101"))
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed102")
_NEW_ID = UUID("01900000-0000-7000-8000-000000fed103")
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed199"))
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/signing#v1"
_PUBLIC_REF = "vault://kv/cora/federation/aps-2bm/signing/pub#v1"


def _command(**overrides: object) -> RegisterCredential:
    base: dict[str, object] = {
        "facility_id": "aps-2bm",
        "audience": "peer.example.org",
        "purpose": CredentialPurpose.SIGNING,
        "secret_ref": _SECRET_REF,
        "public_material_ref": _PUBLIC_REF,
        "expires_at": _EXPIRES_AT,
    }
    base.update(overrides)
    return RegisterCredential(**base)  # type: ignore[arg-type]


def _existing_state() -> Credential:
    return Credential(
        id=_CREDENTIAL_ID,
        facility_id="aps-2bm",
        audience="peer.example.org",
        purpose=CredentialPurpose.SIGNING,
        secret_ref=_SECRET_REF,
        public_material_ref=_PUBLIC_REF,
        expires_at=_EXPIRES_AT,
        registered_by=_REGISTERED_BY,
        registered_at=_NOW,
        rotation_pending_secret_ref=None,
        rotation_pending_public_material_ref=None,
        status=CredentialStatus.ACTIVE,
    )


@pytest.mark.unit
def test_register_credential_emits_event_for_valid_command() -> None:
    events = register_credential.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.credential_id == _NEW_ID
    assert event.facility_id == "aps-2bm"
    assert event.audience == "peer.example.org"
    assert event.purpose is CredentialPurpose.SIGNING
    assert event.secret_ref == _SECRET_REF
    assert event.public_material_ref == _PUBLIC_REF
    assert event.expires_at == _EXPIRES_AT
    assert event.registered_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_register_credential_accepts_none_expires_at() -> None:
    events = register_credential.decide(
        state=None,
        command=_command(expires_at=None),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].expires_at is None


@pytest.mark.unit
def test_register_credential_accepts_none_public_material_ref() -> None:
    events = register_credential.decide(
        state=None,
        command=_command(public_material_ref=None),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].public_material_ref is None


@pytest.mark.unit
@pytest.mark.parametrize("purpose", list(CredentialPurpose))
def test_register_credential_accepts_every_purpose_arm(purpose: CredentialPurpose) -> None:
    """The decider validates the closed enum at the Pydantic boundary; all
    six arms must reach the event verbatim."""
    events = register_credential.decide(
        state=None,
        command=_command(purpose=purpose),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].purpose is purpose


@pytest.mark.unit
def test_register_credential_trims_facility_id_before_capture() -> None:
    events = register_credential.decide(
        state=None,
        command=_command(facility_id="  aps-2bm  "),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].facility_id == "aps-2bm"


@pytest.mark.unit
def test_register_credential_trims_audience_before_capture() -> None:
    events = register_credential.decide(
        state=None,
        command=_command(audience="  peer.example.org  "),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].audience == "peer.example.org"


@pytest.mark.unit
def test_register_credential_trims_secret_ref_before_capture() -> None:
    events = register_credential.decide(
        state=None,
        command=_command(secret_ref=f"  {_SECRET_REF}  "),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].secret_ref == _SECRET_REF


@pytest.mark.unit
def test_register_credential_rejects_when_state_already_exists() -> None:
    """Genesis-only: a non-None state surfaces CredentialAlreadyExistsError."""
    with pytest.raises(CredentialAlreadyExistsError) as exc:
        register_credential.decide(
            state=_existing_state(),
            command=_command(),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.credential_id == _CREDENTIAL_ID


@pytest.mark.unit
def test_register_credential_rejects_empty_facility_id() -> None:
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        register_credential.decide(
            state=None,
            command=_command(facility_id=""),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "facility_id"
    assert "facility_id" in str(exc.value)


@pytest.mark.unit
def test_register_credential_rejects_whitespace_only_facility_id() -> None:
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        register_credential.decide(
            state=None,
            command=_command(facility_id="   "),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "facility_id"
    assert exc.value.value == "   "


@pytest.mark.unit
def test_register_credential_rejects_empty_audience() -> None:
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        register_credential.decide(
            state=None,
            command=_command(audience=""),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "audience"
    assert "audience" in str(exc.value)


@pytest.mark.unit
def test_register_credential_rejects_whitespace_only_audience() -> None:
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        register_credential.decide(
            state=None,
            command=_command(audience="   "),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "audience"
    assert exc.value.value == "   "


@pytest.mark.unit
def test_register_credential_rejects_empty_secret_ref() -> None:
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        register_credential.decide(
            state=None,
            command=_command(secret_ref=""),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "secret_ref"
    assert "secret_ref" in str(exc.value)


@pytest.mark.unit
def test_register_credential_rejects_whitespace_only_secret_ref() -> None:
    with pytest.raises(InvalidCredentialSecretRefError) as exc:
        register_credential.decide(
            state=None,
            command=_command(secret_ref="   \t  "),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.field_name == "secret_ref"
    assert exc.value.value == "   \t  "


@pytest.mark.unit
def test_register_credential_rejects_expires_at_in_the_past() -> None:
    with pytest.raises(CredentialExpiredError) as exc:
        register_credential.decide(
            state=None,
            command=_command(expires_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.credential_id == _NEW_ID


@pytest.mark.unit
def test_register_credential_rejects_expires_at_equal_to_now() -> None:
    """Strict inequality: expires_at must be > now."""
    with pytest.raises(CredentialExpiredError):
        register_credential.decide(
            state=None,
            command=_command(expires_at=_NOW),
            now=_NOW,
            new_id=_NEW_ID,
            registered_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_register_credential_is_pure_same_inputs_same_outputs() -> None:
    first = register_credential.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    second = register_credential.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_register_credential_uses_handler_injected_new_id_verbatim() -> None:
    """Sanity: handler-injected new_id is used; decider does not call uuid4()."""
    new_id = uuid4()
    events = register_credential.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=new_id,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].credential_id == new_id


@pytest.mark.unit
def test_register_credential_uses_handler_injected_actor_id_verbatim() -> None:
    injected = ActorId(uuid4())
    events = register_credential.decide(
        state=None,
        command=_command(),
        now=_NOW,
        new_id=_NEW_ID,
        registered_by=injected,
    )
    assert events[0].registered_by == injected


@pytest.mark.unit
def test_register_credential_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    custom_expiry = datetime(2027, 6, 1, 0, 0, 0, tzinfo=UTC)
    events = register_credential.decide(
        state=None,
        command=_command(expires_at=custom_expiry),
        now=custom_now,
        new_id=_NEW_ID,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now
