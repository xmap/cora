"""Property-based tests for ``record_attestation.decide``.

Universal claims across generated inputs:

  - state=None + valid ChecksumVerified+Match command + matching
    context emits a single AttestationRecorded carrying the injected
    ids / now / canonical evidence.
  - state=Attestation always raises AttestationAlreadyExistsError.
  - kind in {FormatValidated, BitRotChecked} with distribution_id set
    always raises AttestationKindNotYetSupportedError (decider-tier
    defensive path mirrors the handler-tier rejection).
  - kind=ConformsToValidated with distribution_id set always raises
    AttestationKindRejectsDistributionError.
  - Match with evidence_computed_checksum != distribution.checksum
    always raises AttestationChecksumEvidenceMismatchError.
  - Pure: same args produce same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cora.data.aggregates.attestation import (
    Attestation,
    AttestationAlreadyExistsError,
    AttestationChecksumEvidenceMismatchError,
    AttestationKind,
    AttestationKindNotYetSupportedError,
    AttestationKindRejectsDistributionError,
    AttestationOutcome,
    AttestationRecorded,
    AttestationStatus,
    ChecksumVerifiedEvidence,
)
from cora.data.aggregates.dataset import (
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetStatus,
    DatasetUri,
)
from cora.data.aggregates.distribution import (
    AccessProtocol,
    Distribution,
    DistributionStatus,
    DistributionUri,
)
from cora.data.features import record_attestation
from cora.data.features.record_attestation import (
    AttestationRecordingContext,
    AttestationRecordingInput,
)
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA = "a" * 64
_OTHER_SHA = "b" * 64


def _hex_chars() -> st.SearchStrategy[str]:
    return st.from_regex(r"\A[0-9a-f]{64}\Z", fullmatch=True)


def _dataset(dataset_id: UUID) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://bucket/seed"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=DatasetStatus.REGISTERED,
    )


def _distribution(
    distribution_id: UUID,
    dataset_id: UUID,
    *,
    checksum_value: str = _GOOD_SHA,
    now: datetime | None = None,
) -> Distribution:
    return Distribution(
        id=distribution_id,
        dataset_id=dataset_id,
        supply_id=distribution_id,
        uri=DistributionUri("s3://bucket/d.h5"),
        checksum=DatasetChecksum(algorithm="sha256", value=checksum_value),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        access_protocol=AccessProtocol.S3,
        registered_at=now or aware_datetimes().example(),
        registered_by=ActorId(distribution_id),
        status=DistributionStatus.REGISTERED,
    )


def _existing(attestation_id: UUID, now: datetime) -> Attestation:
    return Attestation(
        id=attestation_id,
        dataset_id=attestation_id,
        distribution_id=attestation_id,
        kind=AttestationKind.CHECKSUM_VERIFIED,
        outcome=AttestationOutcome.MATCH,
        evidence=ChecksumVerifiedEvidence(
            expected_checksum=_GOOD_SHA,
            computed_checksum=_GOOD_SHA,
            algorithm="sha256",
            verifier_supply_id=attestation_id,
            verifier_kind="HttpRangeChecksum",
        ),
        attested_at=now,
        attested_by=ActorId(attestation_id),
        status=AttestationStatus.RECORDED,
    )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    dataset_id=st.uuids(),
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    attested_by=st.uuids(),
)
def test_record_attestation_happy_match_emits_one_event(
    dataset_id: UUID,
    distribution_id: UUID,
    supply_id: UUID,
    now: datetime,
    new_id: UUID,
    attested_by: UUID,
) -> None:
    cmd = AttestationRecordingInput(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
        outcome="Match",
        evidence_expected_checksum=_GOOD_SHA,
        evidence_computed_checksum=_GOOD_SHA,
        evidence_algorithm="sha256",
        evidence_verifier_supply_id=supply_id,
        evidence_verifier_kind="HttpRangeChecksum",
        evidence_error_detail=None,
    )
    ctx = AttestationRecordingContext(
        dataset=_dataset(dataset_id),
        distribution=_distribution(distribution_id, dataset_id, now=now),
    )
    events = record_attestation.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=now,
        new_id=new_id,
        attested_by=ActorId(attested_by),
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AttestationRecorded)
    assert event.attestation_id == new_id
    assert event.dataset_id == dataset_id
    assert event.distribution_id == distribution_id
    assert event.kind == "ChecksumVerified"
    assert event.outcome == "Match"
    assert event.occurred_at == now
    assert event.attested_by == ActorId(attested_by)


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    existing_id=st.uuids(),
    dataset_id=st.uuids(),
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_record_attestation_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    dataset_id: UUID,
    distribution_id: UUID,
    supply_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    cmd = AttestationRecordingInput(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
        outcome="Match",
        evidence_expected_checksum=_GOOD_SHA,
        evidence_computed_checksum=_GOOD_SHA,
        evidence_algorithm="sha256",
        evidence_verifier_supply_id=supply_id,
        evidence_verifier_kind="HttpRangeChecksum",
        evidence_error_detail=None,
    )
    ctx = AttestationRecordingContext(
        dataset=_dataset(dataset_id),
        distribution=_distribution(distribution_id, dataset_id, now=now),
    )
    existing = _existing(existing_id, now)
    with pytest.raises(AttestationAlreadyExistsError) as exc:
        record_attestation.decide(
            state=existing,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            attested_by=ActorId(new_id),
        )
    assert exc.value.attestation_id == existing_id


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    dataset_id=st.uuids(),
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    kind=st.sampled_from(["FormatValidated", "BitRotChecked"]),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_record_attestation_unsupported_byte_level_kind_always_raises(
    dataset_id: UUID,
    distribution_id: UUID,
    supply_id: UUID,
    kind: str,
    now: datetime,
    new_id: UUID,
) -> None:
    cmd = AttestationRecordingInput(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind=kind,
        outcome="Match",
        evidence_expected_checksum=_GOOD_SHA,
        evidence_computed_checksum=_GOOD_SHA,
        evidence_algorithm="sha256",
        evidence_verifier_supply_id=supply_id,
        evidence_verifier_kind="HttpRangeChecksum",
        evidence_error_detail=None,
    )
    ctx = AttestationRecordingContext(
        dataset=_dataset(dataset_id),
        distribution=_distribution(distribution_id, dataset_id, now=now),
    )
    with pytest.raises(AttestationKindNotYetSupportedError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            attested_by=ActorId(new_id),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    dataset_id=st.uuids(),
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_record_attestation_conforms_to_with_distribution_always_raises_rejects(
    dataset_id: UUID,
    distribution_id: UUID,
    supply_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    cmd = AttestationRecordingInput(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ConformsToValidated",
        outcome="Match",
        evidence_expected_checksum=_GOOD_SHA,
        evidence_computed_checksum=_GOOD_SHA,
        evidence_algorithm="sha256",
        evidence_verifier_supply_id=supply_id,
        evidence_verifier_kind="ConformsToProbe",
        evidence_error_detail=None,
    )
    ctx = AttestationRecordingContext(
        dataset=_dataset(dataset_id),
        distribution=_distribution(distribution_id, dataset_id, now=now),
    )
    with pytest.raises(AttestationKindRejectsDistributionError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            attested_by=ActorId(new_id),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    dataset_id=st.uuids(),
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    computed=_hex_chars(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_record_attestation_match_with_differing_computed_raises_belt_and_braces(
    dataset_id: UUID,
    distribution_id: UUID,
    supply_id: UUID,
    computed: str,
    now: datetime,
    new_id: UUID,
) -> None:
    # Only test the property when the generated computed differs from
    # the canonical Distribution checksum (the property is "Match with
    # any differing value raises").
    if computed == _GOOD_SHA:
        return
    cmd = AttestationRecordingInput(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
        outcome="Match",
        evidence_expected_checksum=_GOOD_SHA,
        evidence_computed_checksum=computed,
        evidence_algorithm="sha256",
        evidence_verifier_supply_id=supply_id,
        evidence_verifier_kind="HttpRangeChecksum",
        evidence_error_detail=None,
    )
    ctx = AttestationRecordingContext(
        dataset=_dataset(dataset_id),
        distribution=_distribution(distribution_id, dataset_id, now=now),
    )
    with pytest.raises(AttestationChecksumEvidenceMismatchError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            attested_by=ActorId(new_id),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    dataset_id=st.uuids(),
    distribution_id=st.uuids(),
    supply_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    attested_by=st.uuids(),
)
def test_record_attestation_is_pure_same_input_same_output(
    dataset_id: UUID,
    distribution_id: UUID,
    supply_id: UUID,
    now: datetime,
    new_id: UUID,
    attested_by: UUID,
) -> None:
    cmd = AttestationRecordingInput(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
        outcome="Match",
        evidence_expected_checksum=_GOOD_SHA,
        evidence_computed_checksum=_GOOD_SHA,
        evidence_algorithm="sha256",
        evidence_verifier_supply_id=supply_id,
        evidence_verifier_kind="HttpRangeChecksum",
        evidence_error_detail=None,
    )
    ctx = AttestationRecordingContext(
        dataset=_dataset(dataset_id),
        distribution=_distribution(distribution_id, dataset_id, now=now),
    )
    first = record_attestation.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=now,
        new_id=new_id,
        attested_by=ActorId(attested_by),
    )
    second = record_attestation.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=now,
        new_id=new_id,
        attested_by=ActorId(attested_by),
    )
    assert first == second
