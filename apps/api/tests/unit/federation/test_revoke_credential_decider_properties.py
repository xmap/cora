"""Property-based tests for `revoke_credential.decide` (Federation BC).

Complements the example-based `test_revoke_credential_decider.py` with
universal claims across generated inputs. The decider is a pure
widest-source terminal transition

    (state, command, now, revoked_by) -> list[CredentialRevoked]

Load-bearing properties:

  - state=None always raises `CredentialNotFoundError` carrying
    command.credential_id (existence / genesis guard).
  - The source-state partition is total over `CredentialStatus`: every
    non-Revoked status (Active, Rotating) emits exactly one
    `CredentialRevoked` (credential_id=state.id, occurred_at=now), and
    the lone disallowed source (Revoked) raises
    `CredentialCannotRevokeError` carrying state.id, so a future status
    value cannot silently fall through.
  - The handler-injected `revoked_by` and `now` thread verbatim onto the
    emitted event; `credential_id` is `state.id`, never command.credential_id.
  - Pure: same (state, command, now, revoked_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_FACILITY_CODE = FacilityCode("aps-2bm")
_AUDIENCE = "peer-acme"
_SECRET_REF = "vault://current/v1"
_PUBLIC_MATERIAL_REF = "vault://current/pub/v1"
_PENDING_SECRET_REF = "vault://pending/v2"
_PENDING_PUBLIC_MATERIAL_REF = "vault://pending/pub/v2"
_EXPIRES_AT = None
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed199"))

_REVOCABLE_SOURCES = (CredentialStatus.ACTIVE, CredentialStatus.ROTATING)
_DISALLOWED_SOURCES = tuple(s for s in CredentialStatus if s not in frozenset(_REVOCABLE_SOURCES))


def _credential(
    *,
    credential_id: UUID,
    status: CredentialStatus,
    registered_at: datetime,
) -> Credential:
    rotating = status is CredentialStatus.ROTATING
    return Credential(
        id=credential_id,
        facility_code=_FACILITY_CODE,
        audience=_AUDIENCE,
        purpose=CredentialPurpose.SIGNING,
        secret_ref=_SECRET_REF,
        public_material_ref=_PUBLIC_MATERIAL_REF,
        expires_at=_EXPIRES_AT,
        registered_by=_REGISTERED_BY,
        registered_at=registered_at,
        rotation_pending_secret_ref=_PENDING_SECRET_REF if rotating else None,
        rotation_pending_public_material_ref=(_PENDING_PUBLIC_MATERIAL_REF if rotating else None),
        status=status,
    )


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    reason=st.none() | printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_revoke_with_none_state_always_raises_not_found(
    credential_id: UUID,
    reason: str | None,
    now: datetime,
) -> None:
    """Empty stream always raises `CredentialNotFoundError` carrying command id."""
    with pytest.raises(CredentialNotFoundError) as exc:
        revoke_credential.decide(
            state=None,
            command=RevokeCredential(credential_id=credential_id, reason=reason),
            now=now,
            revoked_by=credential_id,
        )
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    source=st.sampled_from(_REVOCABLE_SOURCES),
    revoked_by=st.uuids(),
    reason=st.none() | printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_revoke_from_any_non_revoked_source_emits_single_event(
    credential_id: UUID,
    source: CredentialStatus,
    revoked_by: UUID,
    reason: str | None,
    now: datetime,
) -> None:
    """Every non-Revoked source emits exactly one CredentialRevoked."""
    events = revoke_credential.decide(
        state=_credential(credential_id=credential_id, status=source, registered_at=now),
        command=RevokeCredential(credential_id=credential_id, reason=reason),
        now=now,
        revoked_by=revoked_by,
    )
    assert events == [
        CredentialRevoked(
            credential_id=credential_id,
            revoked_by=revoked_by,
            occurred_at=now,
            reason=reason,
        )
    ]


@pytest.mark.unit
@given(
    credential_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    revoked_by=st.uuids(),
    now=aware_datetimes(),
)
def test_revoke_from_disallowed_source_always_raises_cannot_revoke(
    credential_id: UUID,
    source: CredentialStatus,
    revoked_by: UUID,
    now: datetime,
) -> None:
    """The lone Revoked source raises, carrying state.id."""
    with pytest.raises(CredentialCannotRevokeError) as exc:
        revoke_credential.decide(
            state=_credential(credential_id=credential_id, status=source, registered_at=now),
            command=RevokeCredential(credential_id=credential_id),
            now=now,
            revoked_by=revoked_by,
        )
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    state_id=st.uuids(),
    command_id=st.uuids(),
    revoked_by=st.uuids(),
    now=aware_datetimes(),
)
def test_revoke_uses_state_id_not_command_credential_id(
    state_id: UUID,
    command_id: UUID,
    revoked_by: UUID,
    now: datetime,
) -> None:
    """The emitted event's credential_id is state.id, not command.credential_id."""
    assume(state_id != command_id)
    events = revoke_credential.decide(
        state=_credential(
            credential_id=state_id, status=CredentialStatus.ACTIVE, registered_at=now
        ),
        command=RevokeCredential(credential_id=command_id),
        now=now,
        revoked_by=revoked_by,
    )
    assert events[0].credential_id == state_id


@pytest.mark.unit
@given(credential_id=st.uuids(), revoked_by=st.uuids(), now=aware_datetimes())
def test_revoke_threads_injected_revoked_by_and_now_onto_event(
    credential_id: UUID,
    revoked_by: UUID,
    now: datetime,
) -> None:
    """Handler-injected `revoked_by` and `now` are captured verbatim, not recomputed."""
    events = revoke_credential.decide(
        state=_credential(
            credential_id=credential_id, status=CredentialStatus.ACTIVE, registered_at=now
        ),
        command=RevokeCredential(credential_id=credential_id),
        now=now,
        revoked_by=revoked_by,
    )
    assert events[0].revoked_by == revoked_by
    assert events[0].occurred_at == now


@pytest.mark.unit
@given(credential_id=st.uuids(), revoked_by=st.uuids(), now=aware_datetimes())
def test_revoke_is_pure_same_input_same_output(
    credential_id: UUID,
    revoked_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _credential(
        credential_id=credential_id, status=CredentialStatus.ACTIVE, registered_at=now
    )
    command = RevokeCredential(credential_id=credential_id)
    first = revoke_credential.decide(state=state, command=command, now=now, revoked_by=revoked_by)
    second = revoke_credential.decide(state=state, command=command, now=now, revoked_by=revoked_by)
    assert first == second
