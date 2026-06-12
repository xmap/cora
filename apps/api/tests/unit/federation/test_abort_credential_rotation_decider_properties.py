"""Property-based tests for `abort_credential_rotation.decide` (Federation BC).

Complements the example-based `test_abort_credential_rotation_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now, rotation_aborted_by) -> list[CredentialRotationAborted]

Load-bearing properties:

  - state=None always raises `CredentialNotFoundError` carrying
    command.credential_id.
  - The source-state partition is total over `CredentialStatus`: only
    `Rotating` emits exactly one `CredentialRotationAborted`
    (credential_id=state.id, occurred_at=now); every other status raises
    `CredentialCannotRotateError` carrying the current status and
    attempted='abort_rotation', so a future status value cannot silently
    fall through.
  - The emitted event's credential_id is `state.id`, never
    `command.credential_id`.
  - Handler-injected `rotation_aborted_by` and `now` are threaded onto
    the event verbatim.
  - Pure: same (state, command, now, rotation_aborted_by) returns equal
    events.
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
    CredentialRotationAborted,
    CredentialStatus,
)
from cora.federation.features import abort_credential_rotation
from cora.federation.features.abort_credential_rotation import (
    AbortCredentialRotation,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))

_ABORTABLE_SOURCES = (CredentialStatus.ROTATING,)
_DISALLOWED_SOURCES = tuple(s for s in CredentialStatus if s not in frozenset(_ABORTABLE_SOURCES))


def _credential(*, credential_id: UUID, status: CredentialStatus) -> Credential:
    return Credential(
        id=credential_id,
        facility_code=FacilityCode("aps-2bm"),
        audience="peer-acme",
        purpose=CredentialPurpose.SIGNING,
        secret_ref="vault://current/v1",
        public_material_ref="vault://current/pub/v1",
        expires_at=_EXPIRES_AT,
        registered_by=_REGISTERED_BY,
        registered_at=_REGISTERED_AT,
        rotation_pending_secret_ref="vault://pending/v2",
        rotation_pending_public_material_ref="vault://pending/pub/v2",
        status=status,
    )


def _command(*, credential_id: UUID, reason: str | None = None) -> AbortCredentialRotation:
    return AbortCredentialRotation(
        credential_id=credential_id,
        aborted_by=UUID(int=7),
        reason=reason,
    )


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    aborted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_abort_with_none_state_always_raises_not_found(
    credential_id: UUID,
    aborted_by: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `CredentialNotFoundError` carrying credential_id."""
    with pytest.raises(CredentialNotFoundError) as exc:
        abort_credential_rotation.decide(
            state=None,
            command=_command(credential_id=credential_id),
            now=now,
            rotation_aborted_by=aborted_by,
        )
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    aborted_by=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_abort_from_rotating_emits_single_event(
    credential_id: UUID,
    aborted_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Rotating is the only abortable source; emits one CredentialRotationAborted."""
    events = abort_credential_rotation.decide(
        state=_credential(credential_id=credential_id, status=CredentialStatus.ROTATING),
        command=_command(credential_id=credential_id, reason=reason),
        now=now,
        rotation_aborted_by=aborted_by,
    )
    assert events == [
        CredentialRotationAborted(
            credential_id=credential_id,
            rotation_aborted_by=aborted_by,
            occurred_at=now,
            reason=reason,
        )
    ]


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    aborted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_abort_from_disallowed_source_always_raises_cannot_rotate(
    credential_id: UUID,
    source: CredentialStatus,
    aborted_by: UUID,
    now: datetime,
) -> None:
    """Any source other than Rotating raises, carrying status and attempted verb."""
    with pytest.raises(CredentialCannotRotateError) as exc:
        abort_credential_rotation.decide(
            state=_credential(credential_id=credential_id, status=source),
            command=_command(credential_id=credential_id),
            now=now,
            rotation_aborted_by=aborted_by,
        )
    assert exc.value.current_status is source
    assert exc.value.attempted == "abort_rotation"


@pytest.mark.unit
@given(
    state_credential_id=st.uuids(),
    command_credential_id=st.uuids(),
    aborted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_abort_uses_state_id_not_command_credential_id(
    state_credential_id: UUID,
    command_credential_id: UUID,
    aborted_by: UUID,
    now: datetime,
) -> None:
    """The emitted event's credential_id is state.id, not command.credential_id."""
    assume(state_credential_id != command_credential_id)
    events = abort_credential_rotation.decide(
        state=_credential(credential_id=state_credential_id, status=CredentialStatus.ROTATING),
        command=_command(credential_id=command_credential_id),
        now=now,
        rotation_aborted_by=aborted_by,
    )
    assert events[0].credential_id == state_credential_id


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    aborted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_abort_threads_injected_actor_and_clock_onto_event(
    credential_id: UUID,
    aborted_by: UUID,
    now: datetime,
) -> None:
    """Handler-injected `rotation_aborted_by` and `now` land on the event verbatim."""
    events = abort_credential_rotation.decide(
        state=_credential(credential_id=credential_id, status=CredentialStatus.ROTATING),
        command=_command(credential_id=credential_id),
        now=now,
        rotation_aborted_by=aborted_by,
    )
    assert events[0].rotation_aborted_by == aborted_by
    assert events[0].occurred_at == now


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    aborted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_abort_is_pure_same_input_same_output(
    credential_id: UUID,
    aborted_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _credential(credential_id=credential_id, status=CredentialStatus.ROTATING)
    command = _command(credential_id=credential_id)
    first = abort_credential_rotation.decide(
        state=state, command=command, now=now, rotation_aborted_by=aborted_by
    )
    second = abort_credential_rotation.decide(
        state=state, command=command, now=now, rotation_aborted_by=aborted_by
    )
    assert first == second
