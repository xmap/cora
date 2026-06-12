"""Property-based tests for `complete_credential_rotation.decide` (Federation BC).

Complements the example-based `test_complete_credential_rotation_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now, rotation_completed_by) -> list[CredentialRotationCompleted]

The Credential aggregate is keyed by a uuid `id`; `facility_code` is a
fixed `FacilityCode` slug copied from the example test, and every
secret-ref / opaque-pointer value is a fixed valid literal. Only ids +
clock + status are generated.

Load-bearing properties:

  - state=None always raises `CredentialNotFoundError` carrying
    command.credential_id (existence / genesis guard).
  - The source-state partition is total over `CredentialStatus`: only
    `Rotating` (with a populated pending secret ref) emits exactly one
    `CredentialRotationCompleted`; every other status raises
    `CredentialCannotRotateError` carrying the current status, so a
    future status value cannot silently fall through.
  - The belt-and-braces invariant holds: a `Rotating` credential whose
    pending secret ref is `None` raises `CredentialCannotRotateError`
    rather than promoting `None` to current.
  - The emitted event's credential_id is `state.id`, never
    command.credential_id; `rotation_completed_by` and `occurred_at` are
    threaded verbatim from the handler-injected non-determinism.
  - Pure: same (state, command, now, rotation_completed_by) returns
    equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_FACILITY_CODE = FacilityCode("aps-2bm")
_AUDIENCE = "peer-acme"
_SECRET_REF = "vault://current/v1"
_PUBLIC_MATERIAL_REF = "vault://current/pub/v1"
_PENDING_SECRET_REF = "vault://pending/v2"
_PENDING_PUBLIC_MATERIAL_REF = "vault://pending/pub/v2"
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))
_REGISTERED_AT = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)

_COMPLETABLE_SOURCES = (CredentialStatus.ROTATING,)
_DISALLOWED_SOURCES = tuple(s for s in CredentialStatus if s not in frozenset(_COMPLETABLE_SOURCES))


def _credential(
    *,
    credential_id: UUID,
    status: CredentialStatus,
    pending_secret_ref: str | None = _PENDING_SECRET_REF,
) -> Credential:
    return Credential(
        id=credential_id,
        facility_code=_FACILITY_CODE,
        audience=_AUDIENCE,
        purpose=CredentialPurpose.SIGNING,
        secret_ref=_SECRET_REF,
        public_material_ref=_PUBLIC_MATERIAL_REF,
        expires_at=None,
        registered_by=_REGISTERED_BY,
        registered_at=_REGISTERED_AT,
        rotation_pending_secret_ref=pending_secret_ref,
        rotation_pending_public_material_ref=_PENDING_PUBLIC_MATERIAL_REF,
        status=status,
    )


def _command(credential_id: UUID) -> CompleteCredentialRotation:
    return CompleteCredentialRotation(credential_id=credential_id)


@pytest.mark.unit
@given(credential_id=st.uuids(), now=aware_datetimes(), actor=st.uuids())
def test_complete_credential_rotation_with_none_state_always_raises_not_found(
    credential_id: UUID,
    now: datetime,
    actor: UUID,
) -> None:
    """Empty stream always raises CredentialNotFoundError carrying command.credential_id."""
    with pytest.raises(CredentialNotFoundError) as exc:
        complete_credential_rotation.decide(
            state=None,
            command=_command(credential_id),
            now=now,
            rotation_completed_by=actor,
        )
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(credential_id=st.uuids(), now=aware_datetimes(), actor=st.uuids())
def test_complete_credential_rotation_from_rotating_emits_single_event(
    credential_id: UUID,
    now: datetime,
    actor: UUID,
) -> None:
    """Rotating is the only completable source; emits one CredentialRotationCompleted."""
    events = complete_credential_rotation.decide(
        state=_credential(credential_id=credential_id, status=CredentialStatus.ROTATING),
        command=_command(credential_id),
        now=now,
        rotation_completed_by=actor,
    )
    assert events == [
        CredentialRotationCompleted(
            credential_id=credential_id,
            rotation_completed_by=actor,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_complete_credential_rotation_from_disallowed_source_always_raises_cannot_rotate(
    credential_id: UUID,
    source: CredentialStatus,
    now: datetime,
    actor: UUID,
) -> None:
    """Any source other than Rotating raises, carrying the current status."""
    with pytest.raises(CredentialCannotRotateError) as exc:
        complete_credential_rotation.decide(
            state=_credential(credential_id=credential_id, status=source),
            command=_command(credential_id),
            now=now,
            rotation_completed_by=actor,
        )
    assert exc.value.current_status is source
    assert exc.value.attempted == "complete_rotation"


@pytest.mark.unit
@given(credential_id=st.uuids(), now=aware_datetimes(), actor=st.uuids())
def test_complete_credential_rotation_with_none_pending_secret_ref_raises_cannot_rotate(
    credential_id: UUID,
    now: datetime,
    actor: UUID,
) -> None:
    """A Rotating credential whose pending secret ref is None rejects rather than
    promoting None to current."""
    with pytest.raises(CredentialCannotRotateError) as exc:
        complete_credential_rotation.decide(
            state=_credential(
                credential_id=credential_id,
                status=CredentialStatus.ROTATING,
                pending_secret_ref=None,
            ),
            command=_command(credential_id),
            now=now,
            rotation_completed_by=actor,
        )
    assert exc.value.attempted == "complete_rotation"
    assert exc.value.current_status is CredentialStatus.ROTATING


@pytest.mark.unit
@given(
    state_id=st.uuids(),
    command_credential_id=st.uuids(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_complete_credential_rotation_uses_state_id_not_command_credential_id(
    state_id: UUID,
    command_credential_id: UUID,
    now: datetime,
    actor: UUID,
) -> None:
    """The emitted event's credential_id is state.id, not command.credential_id."""
    assume(state_id != command_credential_id)
    events = complete_credential_rotation.decide(
        state=_credential(credential_id=state_id, status=CredentialStatus.ROTATING),
        command=_command(command_credential_id),
        now=now,
        rotation_completed_by=actor,
    )
    assert events[0].credential_id == state_id


@pytest.mark.unit
@given(credential_id=st.uuids(), now=aware_datetimes(), actor=st.uuids())
def test_complete_credential_rotation_threads_injected_actor_and_clock_verbatim(
    credential_id: UUID,
    now: datetime,
    actor: UUID,
) -> None:
    """Handler-injected rotation_completed_by and now land on the event unchanged."""
    events = complete_credential_rotation.decide(
        state=_credential(credential_id=credential_id, status=CredentialStatus.ROTATING),
        command=_command(credential_id),
        now=now,
        rotation_completed_by=actor,
    )
    assert events[0].rotation_completed_by == actor
    assert events[0].occurred_at == now


@pytest.mark.unit
@given(credential_id=st.uuids(), now=aware_datetimes(), actor=st.uuids())
def test_complete_credential_rotation_is_pure_same_input_same_output(
    credential_id: UUID,
    now: datetime,
    actor: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _credential(credential_id=credential_id, status=CredentialStatus.ROTATING)
    command = _command(credential_id)
    first = complete_credential_rotation.decide(
        state=state, command=command, now=now, rotation_completed_by=actor
    )
    second = complete_credential_rotation.decide(
        state=state, command=command, now=now, rotation_completed_by=actor
    )
    assert first == second
