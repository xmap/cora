"""Property-based tests for `sign_seal_pointer.decide` (Federation BC).

Complements the example-based `test_sign_seal_pointer_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source crypto-chain transition with actor attribution

    (state, command, now, signed_by) -> list[SealPointerSigned]

The Seal aggregate is the per-facility singleton keyed by
`facility_code` (a slug `FacilityCode`), not a uuid; identity is
threaded through state, not minted per transition.

Load-bearing properties:

  - state=None always raises `SealNotFoundError` carrying
    command.facility_code.
  - The source-state partition is total over `SealStatus`: only `Live`
    emits exactly one `SealPointerSigned`; every other status raises
    `SealCannotSignError` carrying the current status (and the state's
    facility code).
  - Happy path (Live source, valid head hash, strictly monotonic
    sequence) emits exactly one event whose facility_code is
    state.facility_code, occurred_at == signed_at == now, and signed_by
    threaded verbatim.
  - The emitted event reuses state.facility_code, never a fresh slug.
  - Pure: same (state, command, now, signed_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotSignError,
    SealNotFoundError,
    SealPointerSigned,
    SealStatus,
)
from cora.federation.features import sign_seal_pointer
from cora.federation.features.sign_seal_pointer import SignSealPointer
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_FACILITY_CODE = "aps-2bm"
_PRIOR_HEAD_HASH = "a" * 64
_NEW_HEAD_HASH = "b" * 64
_PRIOR_SEQUENCE_NUMBER = 1
_NEW_SEQUENCE_NUMBER = 2

_SIGNABLE_SOURCES = (SealStatus.LIVE,)
_DISALLOWED_SOURCES = tuple(s for s in SealStatus if s not in frozenset(_SIGNABLE_SOURCES))


def _seal(
    *,
    online_credential_id: UUID,
    offline_credential_id: UUID,
    initialized_by: UUID,
    initialized_at: datetime,
    status: SealStatus,
) -> Seal:
    return Seal(
        facility_code=FacilityCode(_FACILITY_CODE),
        online_credential_id=online_credential_id,
        offline_credential_id=offline_credential_id,
        current_head_hash=_PRIOR_HEAD_HASH,
        current_sequence_number=_PRIOR_SEQUENCE_NUMBER,
        initialized_by=ActorId(initialized_by),
        initialized_at=initialized_at,
        status=status,
    )


def _command() -> SignSealPointer:
    return SignSealPointer(
        facility_code=_FACILITY_CODE,
        new_head_hash=_NEW_HEAD_HASH,
        new_sequence_number=_NEW_SEQUENCE_NUMBER,
    )


@pytest.mark.unit
@given(now=aware_datetimes(), signed_by_uuid=st.uuids())
def test_sign_with_none_state_always_raises_not_found(
    now: datetime,
    signed_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SealNotFoundError` carrying command.facility_code."""
    with pytest.raises(SealNotFoundError) as exc:
        sign_seal_pointer.decide(
            state=None,
            command=_command(),
            now=now,
            signed_by=ActorId(signed_by_uuid),
        )
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(
    online_key=st.uuids(),
    offline_key=st.uuids(),
    initialized_by=st.uuids(),
    initialized_at=aware_datetimes(),
    now=aware_datetimes(),
    signed_by_uuid=st.uuids(),
)
def test_sign_from_live_emits_single_event_threading_injected_fields(
    online_key: UUID,
    offline_key: UUID,
    initialized_by: UUID,
    initialized_at: datetime,
    now: datetime,
    signed_by_uuid: UUID,
) -> None:
    """Live is the only signable source; emits one event with now and signer threaded."""
    signed_by = ActorId(signed_by_uuid)
    state = _seal(
        online_credential_id=online_key,
        offline_credential_id=offline_key,
        initialized_by=initialized_by,
        initialized_at=initialized_at,
        status=SealStatus.LIVE,
    )
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=now,
        signed_by=signed_by,
    )
    assert events == [
        SealPointerSigned(
            facility_code=FacilityCode(_FACILITY_CODE),
            head_hash=_NEW_HEAD_HASH,
            sequence_number=_NEW_SEQUENCE_NUMBER,
            signed_at=now,
            signed_by=signed_by,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    source=st.sampled_from(_DISALLOWED_SOURCES),
    online_key=st.uuids(),
    offline_key=st.uuids(),
    initialized_by=st.uuids(),
    initialized_at=aware_datetimes(),
    now=aware_datetimes(),
    signed_by_uuid=st.uuids(),
)
def test_sign_from_disallowed_source_always_raises_cannot_sign(
    source: SealStatus,
    online_key: UUID,
    offline_key: UUID,
    initialized_by: UUID,
    initialized_at: datetime,
    now: datetime,
    signed_by_uuid: UUID,
) -> None:
    """Any source other than Live raises, carrying the current status and facility code."""
    state = _seal(
        online_credential_id=online_key,
        offline_credential_id=offline_key,
        initialized_by=initialized_by,
        initialized_at=initialized_at,
        status=source,
    )
    with pytest.raises(SealCannotSignError) as exc:
        sign_seal_pointer.decide(
            state=state,
            command=_command(),
            now=now,
            signed_by=ActorId(signed_by_uuid),
        )
    assert exc.value.current_status is source
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(
    online_key=st.uuids(),
    offline_key=st.uuids(),
    initialized_by=st.uuids(),
    initialized_at=aware_datetimes(),
    now=aware_datetimes(),
    signed_by_uuid=st.uuids(),
)
def test_sign_reuses_facility_code_from_state_never_mints(
    online_key: UUID,
    offline_key: UUID,
    initialized_by: UUID,
    initialized_at: datetime,
    now: datetime,
    signed_by_uuid: UUID,
) -> None:
    """The emitted event reuses state.facility_code; only genesis mints identity."""
    state = _seal(
        online_credential_id=online_key,
        offline_credential_id=offline_key,
        initialized_by=initialized_by,
        initialized_at=initialized_at,
        status=SealStatus.LIVE,
    )
    events = sign_seal_pointer.decide(
        state=state,
        command=_command(),
        now=now,
        signed_by=ActorId(signed_by_uuid),
    )
    assert events[0].facility_code == state.facility_code


@pytest.mark.unit
@given(
    online_key=st.uuids(),
    offline_key=st.uuids(),
    initialized_by=st.uuids(),
    initialized_at=aware_datetimes(),
    now=aware_datetimes(),
    signed_by_uuid=st.uuids(),
)
def test_sign_is_pure_same_input_same_output(
    online_key: UUID,
    offline_key: UUID,
    initialized_by: UUID,
    initialized_at: datetime,
    now: datetime,
    signed_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _seal(
        online_credential_id=online_key,
        offline_credential_id=offline_key,
        initialized_by=initialized_by,
        initialized_at=initialized_at,
        status=SealStatus.LIVE,
    )
    command = _command()
    signed_by = ActorId(signed_by_uuid)
    first = sign_seal_pointer.decide(state=state, command=command, now=now, signed_by=signed_by)
    second = sign_seal_pointer.decide(state=state, command=command, now=now, signed_by=signed_by)
    assert first == second
