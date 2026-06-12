"""Property-based tests for `initialize_seal.decide` (Federation BC).

Complements the example-based `test_initialize_seal_decider.py` with
universal claims across generated inputs. `initialize_seal` is a gated
per-facility-singleton genesis returning `list[SealInitialized]`. The
full gate matrix (purpose mismatch, inactive credential, trust-anchor
membership, key collision) is pinned by the example tests; the PBT
asserts only the claims that hold across the whole input space:

  - Any non-None Seal state always raises `SealAlreadyExistsError`
    carrying state.facility_code.value, regardless of clock / actor /
    status (idempotency-as-error; genesis-only singleton guard).
  - On the happy path (all three lookups resolve, both credentials are
    trust anchors with the right purpose and Active status) the single
    `SealInitialized` carries the injected fields: facility_code =
    FacilityCode(command.facility_code), online/offline credential ids
    threaded from the command, initialized_by = the injected actor,
    occurred_at = now.
  - Pure: same inputs return equal results (no clock / id leakage).

A Seal aggregate is keyed by `facility_code` (a slug VO), not a uuid, so
the threaded identity is the FacilityCode, not a generated id. Any
cryptographic / schema-validated value (facility code, credential refs)
is a FIXED valid value copied from the example test; only the clock,
the injected actor id, and (for the existence guard) the prior status
are generated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    Seal,
    SealAlreadyExistsError,
    SealStatus,
)
from cora.federation.features import initialize_seal
from cora.federation.features.initialize_seal import InitializeSeal
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_FACILITY_CODE = "aps-2bm"
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0b1")
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed101"))


def _self_facility(
    *,
    trust_anchors: frozenset[UUID] = frozenset({_ONLINE_KEY_REF, _OFFLINE_KEY_REF}),
) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=FacilityId(facility_stream_id(FacilityCode(_FACILITY_CODE))),
        code=FacilityCode(_FACILITY_CODE),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(CredentialId(cid) for cid in trust_anchors),
    )


def _command(**overrides: object) -> InitializeSeal:
    base: dict[str, object] = {
        "facility_code": _FACILITY_CODE,
        "online_credential_id": _ONLINE_KEY_REF,
        "offline_credential_id": _OFFLINE_KEY_REF,
    }
    base.update(overrides)
    return InitializeSeal(**base)  # type: ignore[arg-type]


def _online_cred(
    credential_id: UUID = _ONLINE_KEY_REF,
    *,
    purpose: str = CredentialPurpose.SEAL_ONLINE_SIGNING.value,
    status: str = CredentialStatus.ACTIVE.value,
    facility_id: str = _FACILITY_CODE,
) -> CredentialLookupResult:
    return CredentialLookupResult(
        id=credential_id,
        facility_id=FacilityCode(facility_id),
        purpose=purpose,
        status=status,
    )


def _offline_cred(
    credential_id: UUID = _OFFLINE_KEY_REF,
    *,
    purpose: str = CredentialPurpose.SEAL_OFFLINE_ROOT.value,
    status: str = CredentialStatus.ACTIVE.value,
    facility_id: str = _FACILITY_CODE,
) -> CredentialLookupResult:
    return CredentialLookupResult(
        id=credential_id,
        facility_id=FacilityCode(facility_id),
        purpose=purpose,
        status=status,
    )


def _existing_state(*, status: SealStatus = SealStatus.LIVE, now: datetime) -> Seal:
    return Seal(
        facility_code=FacilityCode(_FACILITY_CODE),
        online_credential_id=_ONLINE_KEY_REF,
        offline_credential_id=_OFFLINE_KEY_REF,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by=_PRINCIPAL_ID,
        initialized_at=now,
        status=status,
    )


@pytest.mark.unit
@given(
    existing_status=st.sampled_from(list(SealStatus)),
    initialized_by=st.uuids(),
    now=aware_datetimes(),
)
def test_initialize_seal_on_existing_state_always_raises_already_exists(
    existing_status: SealStatus,
    initialized_by: UUID,
    now: datetime,
) -> None:
    """Any non-None Seal state raises SealAlreadyExistsError carrying the facility code."""
    existing = _existing_state(status=existing_status, now=now)
    with pytest.raises(SealAlreadyExistsError) as exc:
        initialize_seal.decide(
            state=existing,
            command=_command(),
            now=now,
            initialized_by=ActorId(initialized_by),
            online_credential=_online_cred(),
            offline_credential=_offline_cred(),
            self_facility=_self_facility(),
        )
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(initialized_by=st.uuids(), now=aware_datetimes())
def test_initialize_seal_happy_path_emits_single_event_with_injected_fields(
    initialized_by: UUID,
    now: datetime,
) -> None:
    """The happy path emits one SealInitialized with the injected actor, clock, and refs."""
    actor = ActorId(initialized_by)
    events = initialize_seal.decide(
        state=None,
        command=_command(),
        now=now,
        initialized_by=actor,
        online_credential=_online_cred(),
        offline_credential=_offline_cred(),
        self_facility=_self_facility(),
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_code == FacilityCode(_FACILITY_CODE)
    assert event.online_credential_id == _ONLINE_KEY_REF
    assert event.offline_credential_id == _OFFLINE_KEY_REF
    assert event.initialized_by == actor
    assert event.occurred_at == now


@pytest.mark.unit
@given(initialized_by=st.uuids(), now=aware_datetimes())
def test_initialize_seal_is_pure_same_inputs_yield_equal_results(
    initialized_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock / id leakage)."""
    actor = ActorId(initialized_by)
    command = _command()
    online = _online_cred()
    offline = _offline_cred()
    self_facility = _self_facility()
    first = initialize_seal.decide(
        state=None,
        command=command,
        now=now,
        initialized_by=actor,
        online_credential=online,
        offline_credential=offline,
        self_facility=self_facility,
    )
    second = initialize_seal.decide(
        state=None,
        command=command,
        now=now,
        initialized_by=actor,
        online_credential=online,
        offline_credential=offline,
        self_facility=self_facility,
    )
    assert first == second
