"""Property-based tests for `rotate_seal_online_key.decide` (Federation BC).

Complements the example-based `test_rotate_seal_online_key_decider.py`
with universal claims across generated inputs. The decider is a pure
cross-aggregate Live -> Live transition with actor attribution

    (state, command, now, rotated_by, new_online_credential,
     self_facility) -> list[SealOnlineKeyRotated]

A Seal is keyed by `facility_code` (a slug), not a uuid; the facility
slug and every cryptographic / schema-validated value is held FIXED at
a valid copy from the example test, and only ids + clock + source
status are generated.

Load-bearing properties:

  - state=None always raises `SealNotFoundError` carrying
    command.facility_code (existence / genesis guard).
  - The source-state partition is total over `SealStatus`: only `Live`
    emits exactly one `SealOnlineKeyRotated`; every other status raises
    `SealCannotRotateError` carrying the current status (the full gate
    matrix is pinned by the example test; this only asserts the clean
    status partition).
  - The emitted event threads the injected fields: facility_code ==
    state.facility_code, new_online_credential_id == command's ref,
    rotated_by threaded verbatim, occurred_at == now.
  - Pure: same inputs return equal events (no clock leakage).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    Seal,
    SealCannotRotateError,
    SealNotFoundError,
    SealOnlineKeyRotated,
    SealStatus,
)
from cora.federation.features import rotate_seal_online_key
from cora.federation.features.rotate_seal_online_key import RotateSealOnlineKey
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_FACILITY_CODE = "aps-2bm"
_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_CURRENT_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0b1")
_INITIALIZED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed199"))

_ROTATABLE_SOURCES = (SealStatus.LIVE,)
_DISALLOWED_SOURCES = tuple(s for s in SealStatus if s not in frozenset(_ROTATABLE_SOURCES))


def _self_facility(new_online_key: UUID) -> FacilityLookupResult:
    """Self-Facility lookup row anchored on the test credentials."""
    return FacilityLookupResult(
        id=FacilityId(facility_stream_id(FacilityCode(_FACILITY_CODE))),
        code=FacilityCode(_FACILITY_CODE),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(
            CredentialId(cid) for cid in (_CURRENT_ONLINE_KEY, _OFFLINE_KEY, new_online_key)
        ),
    )


def _seal(status: SealStatus) -> Seal:
    return Seal(
        facility_code=FacilityCode(_FACILITY_CODE),
        online_credential_id=_CURRENT_ONLINE_KEY,
        offline_credential_id=_OFFLINE_KEY,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by=_INITIALIZED_BY,
        initialized_at=_NOW,
        status=status,
    )


def _command(
    new_online_credential_id: UUID, *, signed_by_offline_root: bool = True
) -> RotateSealOnlineKey:
    return RotateSealOnlineKey(
        facility_code=_FACILITY_CODE,
        new_online_credential_id=new_online_credential_id,
        signed_by_offline_root=signed_by_offline_root,
    )


def _credential(credential_id: UUID) -> CredentialLookupResult:
    return CredentialLookupResult(
        id=credential_id,
        facility_id=FacilityCode(_FACILITY_CODE),
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )


@st.composite
def _fresh_online_keys(draw: st.DrawFn) -> UUID:
    """A generated online-key uuid distinct from the current online + offline refs."""
    key = draw(st.uuids())
    while key in (_CURRENT_ONLINE_KEY, _OFFLINE_KEY):
        key = draw(st.uuids())
    return key


@pytest.mark.unit
@given(new_online_key=st.uuids(), now=aware_datetimes(), rotated_by_uuid=st.uuids())
def test_rotate_with_none_state_always_raises_not_found(
    new_online_key: UUID,
    now: datetime,
    rotated_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SealNotFoundError` carrying command.facility_code."""
    with pytest.raises(SealNotFoundError) as exc:
        rotate_seal_online_key.decide(
            state=None,
            command=_command(new_online_key),
            now=now,
            rotated_by=ActorId(rotated_by_uuid),
            new_online_credential=_credential(new_online_key),
            self_facility=_self_facility(new_online_key),
        )
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(new_online_key=_fresh_online_keys(), now=aware_datetimes(), rotated_by_uuid=st.uuids())
def test_rotate_from_live_emits_single_event(
    new_online_key: UUID,
    now: datetime,
    rotated_by_uuid: UUID,
) -> None:
    """Live is the only rotatable source; emits one SealOnlineKeyRotated."""
    rotated_by = ActorId(rotated_by_uuid)
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(new_online_key),
        now=now,
        rotated_by=rotated_by,
        new_online_credential=_credential(new_online_key),
        self_facility=_self_facility(new_online_key),
    )
    assert events == [
        SealOnlineKeyRotated(
            facility_code=FacilityCode(_FACILITY_CODE),
            new_online_credential_id=new_online_key,
            signed_by_offline_root=True,
            rotated_by=rotated_by,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    new_online_key=_fresh_online_keys(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    rotated_by_uuid=st.uuids(),
)
def test_rotate_from_disallowed_source_always_raises_cannot_rotate(
    new_online_key: UUID,
    source: SealStatus,
    now: datetime,
    rotated_by_uuid: UUID,
) -> None:
    """Any source other than Live raises, carrying the current status."""
    with pytest.raises(SealCannotRotateError) as exc:
        rotate_seal_online_key.decide(
            state=_seal(source),
            command=_command(new_online_key),
            now=now,
            rotated_by=ActorId(rotated_by_uuid),
            new_online_credential=_credential(new_online_key),
            self_facility=_self_facility(new_online_key),
        )
    assert exc.value.current_status is source
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(new_online_key=_fresh_online_keys(), now=aware_datetimes(), rotated_by_uuid=st.uuids())
def test_rotate_threads_injected_fields_onto_emitted_event(
    new_online_key: UUID,
    now: datetime,
    rotated_by_uuid: UUID,
) -> None:
    """Emitted event carries state.facility_code, the command ref, rotated_by, and now."""
    rotated_by = ActorId(rotated_by_uuid)
    state = _seal(SealStatus.LIVE)
    events = rotate_seal_online_key.decide(
        state=state,
        command=_command(new_online_key),
        now=now,
        rotated_by=rotated_by,
        new_online_credential=_credential(new_online_key),
        self_facility=_self_facility(new_online_key),
    )
    event = events[0]
    assert event.facility_code == state.facility_code
    assert event.new_online_credential_id == new_online_key
    assert event.rotated_by == rotated_by
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    new_online_key=_fresh_online_keys(),
    now=aware_datetimes(),
    rotated_by_uuid=st.uuids(),
    signed_by_offline_root=st.booleans(),
)
def test_rotate_records_signed_by_offline_root_verbatim(
    new_online_key: UUID,
    now: datetime,
    rotated_by_uuid: UUID,
    signed_by_offline_root: bool,
) -> None:
    """The offline-root countersignature gesture is recorded verbatim on the event."""
    events = rotate_seal_online_key.decide(
        state=_seal(SealStatus.LIVE),
        command=_command(new_online_key, signed_by_offline_root=signed_by_offline_root),
        now=now,
        rotated_by=ActorId(rotated_by_uuid),
        new_online_credential=_credential(new_online_key),
        self_facility=_self_facility(new_online_key),
    )
    assert events[0].signed_by_offline_root is signed_by_offline_root


@pytest.mark.unit
@given(new_online_key=_fresh_online_keys(), now=aware_datetimes(), rotated_by_uuid=st.uuids())
def test_rotate_is_pure_same_input_same_output(
    new_online_key: UUID,
    now: datetime,
    rotated_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _seal(SealStatus.LIVE)
    command = _command(new_online_key)
    rotated_by = ActorId(rotated_by_uuid)
    credential = _credential(new_online_key)
    self_facility = _self_facility(new_online_key)
    first = rotate_seal_online_key.decide(
        state=state,
        command=command,
        now=now,
        rotated_by=rotated_by,
        new_online_credential=credential,
        self_facility=self_facility,
    )
    second = rotate_seal_online_key.decide(
        state=state,
        command=command,
        now=now,
        rotated_by=rotated_by,
        new_online_credential=credential,
        self_facility=self_facility,
    )
    assert first == second
