"""Property-based tests for `start_credential_rotation.decide` (Federation BC).

Complements the example-based `test_start_credential_rotation_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source transition

    (state, command, now, rotation_started_by) -> list[CredentialRotationStarted]

Load-bearing properties:

  - state=None always raises `CredentialNotFoundError` carrying
    command.credential_id (existence / genesis guard).
  - The source-state partition is total over `CredentialStatus`: only
    `Active` with a valid distinct `new_secret_ref` emits exactly one
    `CredentialRotationStarted` (credential_id=state.id, occurred_at=now);
    every other status raises `CredentialCannotRotateError` carrying the
    current status and `attempted="start_rotation"`, so a future status
    value cannot silently fall through.
  - The emitted event's credential_id is `state.id`, never
    `command.credential_id`; the injected `rotation_started_by` and `now`
    are threaded onto the event verbatim.
  - Pure: same (state, command, now, rotation_started_by) returns equal
    events.

Schema-validated / opaque-pointer values (`secret_ref`, `audience`,
`facility_code`) use FIXED valid values copied from the example test; the
properties generate only ids, the clock, and the source status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialRotationStarted,
    CredentialStatus,
)
from cora.federation.features import start_credential_rotation
from cora.federation.features.start_credential_rotation import (
    StartCredentialRotation,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_FACILITY_CODE = FacilityCode("aps-2bm")
_AUDIENCE = "peer-acme"
_CURRENT_SECRET_REF = "vault://current/v1"
_PUBLIC_MATERIAL_REF = "vault://current/pub/v1"
_PENDING_SECRET_REF = "vault://pending/v2"
_PENDING_PUBLIC_REF = "vault://pending/pub/v2"
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))

_ROTATABLE_SOURCES = (CredentialStatus.ACTIVE,)
_DISALLOWED_SOURCES = tuple(s for s in CredentialStatus if s not in frozenset(_ROTATABLE_SOURCES))


def _credential(
    *,
    credential_id: UUID,
    status: CredentialStatus,
    secret_ref: str = _CURRENT_SECRET_REF,
    registered_at: datetime,
) -> Credential:
    return Credential(
        id=credential_id,
        facility_code=_FACILITY_CODE,
        audience=_AUDIENCE,
        purpose=CredentialPurpose.SIGNING,
        secret_ref=secret_ref,
        public_material_ref=_PUBLIC_MATERIAL_REF,
        expires_at=None,
        registered_by=_REGISTERED_BY,
        registered_at=registered_at,
        rotation_pending_secret_ref=None,
        rotation_pending_public_material_ref=None,
        status=status,
    )


def _command(
    *,
    credential_id: UUID,
    new_secret_ref: str = _PENDING_SECRET_REF,
) -> StartCredentialRotation:
    return StartCredentialRotation(
        credential_id=credential_id,
        new_secret_ref=new_secret_ref,
        new_public_material_ref=_PENDING_PUBLIC_REF,
    )


@pytest.mark.unit
@given(credential_id=st.uuids(), now=aware_datetimes())
def test_start_rotation_with_none_state_always_raises_not_found(
    credential_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `CredentialNotFoundError` carrying the command id."""
    with pytest.raises(CredentialNotFoundError) as exc:
        start_credential_rotation.decide(
            state=None,
            command=_command(credential_id=credential_id),
            now=now,
            rotation_started_by=ActorId(credential_id),
        )
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(credential_id=st.uuids(), actor=st.uuids(), now=aware_datetimes())
def test_start_rotation_from_active_emits_single_event(
    credential_id: UUID,
    actor: UUID,
    now: datetime,
) -> None:
    """Active with a distinct valid new_secret_ref emits one CredentialRotationStarted."""
    events = start_credential_rotation.decide(
        state=_credential(
            credential_id=credential_id,
            status=CredentialStatus.ACTIVE,
            registered_at=now,
        ),
        command=_command(credential_id=credential_id),
        now=now,
        rotation_started_by=ActorId(actor),
    )
    assert events == [
        CredentialRotationStarted(
            credential_id=credential_id,
            pending_secret_ref=_PENDING_SECRET_REF,
            pending_public_material_ref=_PENDING_PUBLIC_REF,
            rotation_started_by=ActorId(actor),
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_start_rotation_from_disallowed_source_always_raises_cannot_rotate(
    credential_id: UUID,
    source: CredentialStatus,
    now: datetime,
) -> None:
    """Any source other than Active raises, carrying the current status and attempt."""
    with pytest.raises(CredentialCannotRotateError) as exc:
        start_credential_rotation.decide(
            state=_credential(
                credential_id=credential_id,
                status=source,
                registered_at=now,
            ),
            command=_command(credential_id=credential_id),
            now=now,
            rotation_started_by=ActorId(credential_id),
        )
    assert exc.value.current_status is source
    assert exc.value.attempted == "start_rotation"


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    new_ref=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_start_rotation_with_same_ref_raises_cannot_rotate(
    credential_id: UUID,
    new_ref: str,
    now: datetime,
) -> None:
    """A new_secret_ref equal to the current secret_ref is rejected loudly."""
    with pytest.raises(CredentialCannotRotateError) as exc:
        start_credential_rotation.decide(
            state=_credential(
                credential_id=credential_id,
                status=CredentialStatus.ACTIVE,
                secret_ref=new_ref,
                registered_at=now,
            ),
            command=_command(credential_id=credential_id, new_secret_ref=new_ref),
            now=now,
            rotation_started_by=ActorId(credential_id),
        )
    assert exc.value.attempted == "start_rotation_same_ref"
    assert exc.value.current_status is CredentialStatus.ACTIVE


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_start_rotation_uses_state_id_not_command_credential_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's credential_id is state.id, not command.credential_id."""
    assume(state_id != command_id)
    events = start_credential_rotation.decide(
        state=_credential(
            credential_id=state_id,
            status=CredentialStatus.ACTIVE,
            registered_at=now,
        ),
        command=_command(credential_id=command_id),
        now=now,
        rotation_started_by=ActorId(state_id),
    )
    assert events[0].credential_id == state_id


@pytest.mark.unit
@given(credential_id=st.uuids(), actor=st.uuids(), now=aware_datetimes())
def test_start_rotation_threads_injected_clock_and_actor_verbatim(
    credential_id: UUID,
    actor: UUID,
    now: datetime,
) -> None:
    """The injected now and rotation_started_by reach the event unaltered."""
    events = start_credential_rotation.decide(
        state=_credential(
            credential_id=credential_id,
            status=CredentialStatus.ACTIVE,
            registered_at=now,
        ),
        command=_command(credential_id=credential_id),
        now=now,
        rotation_started_by=ActorId(actor),
    )
    assert events[0].occurred_at == now
    assert events[0].rotation_started_by == ActorId(actor)


@pytest.mark.unit
@given(credential_id=st.uuids(), actor=st.uuids(), now=aware_datetimes())
def test_start_rotation_is_pure_same_input_same_output(
    credential_id: UUID,
    actor: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _credential(
        credential_id=credential_id,
        status=CredentialStatus.ACTIVE,
        registered_at=now,
    )
    command = _command(credential_id=credential_id)
    first = start_credential_rotation.decide(
        state=state, command=command, now=now, rotation_started_by=ActorId(actor)
    )
    second = start_credential_rotation.decide(
        state=state, command=command, now=now, rotation_started_by=ActorId(actor)
    )
    assert first == second
