"""Property-based tests for `register_credential.decide` (Federation BC).

Complements the example-based `test_register_credential_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id, registered_by) -> list[CredentialRegistered]

Load-bearing properties:

  - Any non-None state always raises `CredentialAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the empty stream the source-state partition is total: state is
    None reaches the happy path, any concrete state raises.
  - On the happy path the single `CredentialRegistered` threads the
    injected / passthrough fields: credential_id=new_id,
    registered_by, facility_code, audience, purpose, secret_ref,
    occurred_at=now.
  - Pure: same inputs return equal events.

A Seal-adjacent Credential binds to a facility_code (a convergent slug),
not a uuid, so facility_code is threaded and asserted as a FacilityCode
VO. Cryptographic / schema-validated values (secret_ref, public
material ref, facility_code, audience) use fixed valid samples copied
from the example test; only ids and the clock are generated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates.credential import (
    Credential,
    CredentialAlreadyExistsError,
    CredentialPurpose,
    CredentialRegistered,
    CredentialStatus,
)
from cora.federation.features import register_credential
from cora.federation.features.register_credential import RegisterCredential
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_FACILITY_CODE = "aps-2bm"
_AUDIENCE = "peer.example.org"
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/signing#v1"
_PUBLIC_REF = "vault://kv/cora/federation/aps-2bm/signing/pub#v1"
_FIXED_REGISTERED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_FIXED_REGISTERED_BY = ActorId(UUID(int=3))
_PURPOSE = st.sampled_from(list(CredentialPurpose))


def _command(**overrides: object) -> RegisterCredential:
    base: dict[str, object] = {
        "facility_code": _FACILITY_CODE,
        "audience": _AUDIENCE,
        "purpose": CredentialPurpose.SIGNING,
        "secret_ref": _SECRET_REF,
        "public_material_ref": _PUBLIC_REF,
        "expires_at": None,
    }
    base.update(overrides)
    return RegisterCredential(**base)  # type: ignore[arg-type]


def _existing_state(*, credential_id: UUID) -> Credential:
    return Credential(
        id=credential_id,
        facility_code=FacilityCode(_FACILITY_CODE),
        audience=_AUDIENCE,
        purpose=CredentialPurpose.SIGNING,
        secret_ref=_SECRET_REF,
        public_material_ref=_PUBLIC_REF,
        expires_at=None,
        registered_by=_FIXED_REGISTERED_BY,
        registered_at=_FIXED_REGISTERED_AT,
        rotation_pending_secret_ref=None,
        rotation_pending_public_material_ref=None,
        status=CredentialStatus.ACTIVE,
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    new_id=st.uuids(),
    registered_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_register_credential_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    new_id: UUID,
    registered_by_uuid: UUID,
    now: datetime,
) -> None:
    """Any non-None state raises CredentialAlreadyExistsError carrying state.id."""
    with pytest.raises(CredentialAlreadyExistsError) as exc:
        register_credential.decide(
            state=_existing_state(credential_id=existing_id),
            command=_command(),
            now=now,
            new_id=new_id,
            registered_by=ActorId(registered_by_uuid),
        )
    assert exc.value.credential_id == existing_id


@pytest.mark.unit
@given(
    new_id=st.uuids(),
    registered_by_uuid=st.uuids(),
    purpose=_PURPOSE,
    now=aware_datetimes(),
)
def test_register_credential_on_empty_stream_emits_single_event_with_threaded_fields(
    new_id: UUID,
    registered_by_uuid: UUID,
    purpose: CredentialPurpose,
    now: datetime,
) -> None:
    """Empty stream emits one CredentialRegistered threading the injected fields."""
    registered_by = ActorId(registered_by_uuid)
    events = register_credential.decide(
        state=None,
        command=_command(purpose=purpose),
        now=now,
        new_id=new_id,
        registered_by=registered_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, CredentialRegistered)
    assert event.credential_id == new_id
    assert event.facility_code == FacilityCode(_FACILITY_CODE)
    assert event.audience == _AUDIENCE
    assert event.purpose is purpose
    assert event.secret_ref == _SECRET_REF
    assert event.public_material_ref == _PUBLIC_REF
    assert event.expires_at is None
    assert event.registered_by == registered_by
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    new_id=st.uuids(),
    registered_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_register_credential_threads_new_id_as_credential_id(
    new_id: UUID,
    registered_by_uuid: UUID,
    now: datetime,
) -> None:
    """The handler-injected new_id reaches credential_id verbatim (no recompute)."""
    events = register_credential.decide(
        state=None,
        command=_command(),
        now=now,
        new_id=new_id,
        registered_by=ActorId(registered_by_uuid),
    )
    assert events[0].credential_id == new_id


@pytest.mark.unit
@given(
    new_id=st.uuids(),
    registered_by_uuid=st.uuids(),
    now=aware_datetimes(),
)
def test_register_credential_is_pure_same_input_same_output(
    new_id: UUID,
    registered_by_uuid: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command()
    registered_by = ActorId(registered_by_uuid)
    first = register_credential.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        registered_by=registered_by,
    )
    second = register_credential.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        registered_by=registered_by,
    )
    assert first == second
