"""Unit tests for the `record_attestation` slice's pure decider.

Genesis-style decider: state must be None (otherwise
AttestationAlreadyExistsError); VOs validate input; context carries the
pre-loaded Dataset (always) and optional Distribution (when
distribution_id was set), both required by the handler before the
decider runs per L17.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.attestation import (
    Attestation,
    AttestationAlreadyExistsError,
    AttestationChecksumEvidenceMismatchError,
    AttestationDistributionDatasetMismatchError,
    AttestationKind,
    AttestationKindNotYetSupportedError,
    AttestationKindRejectsDistributionError,
    AttestationKindRequiresDistributionError,
    AttestationOutcome,
    AttestationStatus,
    AttestationTreeChecksumNotYetSupportedError,
    ChecksumVerifiedEvidence,
    InvalidAttestationEvidenceError,
    InvalidAttestationKindError,
    InvalidAttestationOutcomeError,
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

_GOOD_SHA = "a" * 64
_OTHER_SHA = "b" * 64
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL = ActorId(UUID("01900000-0000-7000-8000-000000000099"))
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da7a")
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000d1571")
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005519")


def _good_command(**overrides: object) -> AttestationRecordingInput:
    base: dict[str, object] = {
        "dataset_id": _DATASET_ID,
        "distribution_id": _DISTRIBUTION_ID,
        "kind": "ChecksumVerified",
        "outcome": "Match",
        "evidence_expected_checksum": _GOOD_SHA,
        "evidence_computed_checksum": _GOOD_SHA,
        "evidence_algorithm": "sha256",
        "evidence_verifier_supply_id": _SUPPLY_ID,
        "evidence_verifier_kind": "HttpRangeChecksum",
        "evidence_error_detail": None,
    }
    base.update(overrides)
    return AttestationRecordingInput(**base)  # type: ignore[arg-type]


def _dataset(
    *,
    dataset_id: UUID = _DATASET_ID,
    checksum_value: str = _GOOD_SHA,
    status: DatasetStatus = DatasetStatus.REGISTERED,
) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed-dataset"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=checksum_value),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


def _distribution(
    *,
    distribution_id: UUID = _DISTRIBUTION_ID,
    dataset_id: UUID = _DATASET_ID,
    checksum_value: str = _GOOD_SHA,
    checksum_algorithm: str = "sha256",
) -> Distribution:
    return Distribution(
        id=distribution_id,
        dataset_id=dataset_id,
        supply_id=_SUPPLY_ID,
        uri=DistributionUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm=checksum_algorithm, value=checksum_value),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        access_protocol=AccessProtocol.S3,
        registered_at=_NOW,
        registered_by=_PRINCIPAL,
        status=DistributionStatus.REGISTERED,
    )


def _context(
    *,
    dataset: Dataset | None = None,
    distribution: Distribution | None = None,
    include_distribution: bool = True,
) -> AttestationRecordingContext:
    return AttestationRecordingContext(
        dataset=dataset or _dataset(),
        distribution=distribution or (_distribution() if include_distribution else None),
    )


def _existing(attestation_id: UUID) -> Attestation:
    return Attestation(
        id=attestation_id,
        dataset_id=_DATASET_ID,
        distribution_id=_DISTRIBUTION_ID,
        kind=AttestationKind.CHECKSUM_VERIFIED,
        outcome=AttestationOutcome.MATCH,
        evidence=ChecksumVerifiedEvidence(
            expected_checksum=_GOOD_SHA,
            computed_checksum=_GOOD_SHA,
            algorithm="sha256",
            verifier_supply_id=_SUPPLY_ID,
            verifier_kind="HttpRangeChecksum",
        ),
        attested_at=_NOW,
        attested_by=_PRINCIPAL,
        status=AttestationStatus.RECORDED,
    )


# ---------- Happy paths ----------


@pytest.mark.unit
def test_decide_emits_attestation_recorded_with_all_fields_on_match() -> None:
    new_id = uuid4()
    cmd = _good_command()
    events = record_attestation.decide(
        state=None,
        command=cmd,
        context=_context(),
        now=_NOW,
        new_id=new_id,
        attested_by=_PRINCIPAL,
    )
    assert len(events) == 1
    event = events[0]
    assert event.attestation_id == new_id
    assert event.dataset_id == cmd.dataset_id
    assert event.distribution_id == cmd.distribution_id
    assert event.kind == "ChecksumVerified"
    assert event.outcome == "Match"
    assert event.evidence["algorithm"] == "sha256"
    assert event.evidence["value"] == _GOOD_SHA
    assert event.evidence["verifier_supply_id"] == str(_SUPPLY_ID)
    assert event.evidence["verifier_kind"] == "HttpRangeChecksum"
    assert "error_detail" not in event.evidence
    assert event.occurred_at == _NOW
    assert event.attested_by == _PRINCIPAL


@pytest.mark.unit
def test_decide_refuses_attestation_of_tree_checksum_distribution() -> None:
    # A directory (sha256-tree) Distribution cannot be verified by the
    # whole-file verifier; recording is refused outright rather than
    # recording a false Mismatch that would flip the Distribution to Stale.
    cmd = _good_command(outcome="Mismatch", evidence_computed_checksum=_OTHER_SHA)
    ctx = _context(distribution=_distribution(checksum_algorithm="sha256-tree"))
    with pytest.raises(AttestationTreeChecksumNotYetSupportedError) as exc:
        record_attestation.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )
    assert exc.value.algorithm == "sha256-tree"


@pytest.mark.unit
def test_decide_emits_mismatch_with_computed_value() -> None:
    cmd = _good_command(outcome="Mismatch", evidence_computed_checksum=_OTHER_SHA)
    events = record_attestation.decide(
        state=None,
        command=cmd,
        context=_context(),
        now=_NOW,
        new_id=uuid4(),
        attested_by=_PRINCIPAL,
    )
    assert events[0].outcome == "Mismatch"
    assert events[0].evidence["value"] == _OTHER_SHA


@pytest.mark.unit
def test_decide_emits_unreachable_with_null_value_and_error_detail() -> None:
    cmd = _good_command(
        outcome="Unreachable",
        evidence_computed_checksum=None,
        evidence_error_detail="HEAD 503",
    )
    events = record_attestation.decide(
        state=None,
        command=cmd,
        context=_context(),
        now=_NOW,
        new_id=uuid4(),
        attested_by=_PRINCIPAL,
    )
    assert events[0].outcome == "Unreachable"
    assert events[0].evidence["value"] is None
    assert events[0].evidence["error_detail"] == "HEAD 503"


# ---------- Closed-enum field validation ----------


@pytest.mark.unit
def test_decide_raises_invalid_kind_for_garbage_string() -> None:
    cmd = _good_command(kind="HashChecked")
    with pytest.raises(InvalidAttestationKindError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


@pytest.mark.unit
def test_decide_raises_invalid_outcome_for_garbage_string() -> None:
    cmd = _good_command(outcome="Pending")
    with pytest.raises(InvalidAttestationOutcomeError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


# ---------- Kind/distribution_id gating ----------


@pytest.mark.unit
def test_decide_raises_kind_requires_distribution_when_id_missing() -> None:
    cmd = _good_command(distribution_id=None)
    with pytest.raises(AttestationKindRequiresDistributionError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(include_distribution=False),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


@pytest.mark.unit
def test_decide_raises_kind_rejects_distribution_for_conforms_to_with_id() -> None:
    cmd = _good_command(kind="ConformsToValidated")
    # ConformsToValidated reaches the not-yet-supported guard at the
    # decider only if it passes the kind/distribution gating; the
    # gating fires first because a Distribution-id was supplied.
    with pytest.raises(AttestationKindRejectsDistributionError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


# ---------- Not-yet-supported kinds ----------


@pytest.mark.unit
def test_decide_raises_kind_not_yet_supported_for_format_validated() -> None:
    cmd = _good_command(kind="FormatValidated")
    with pytest.raises(AttestationKindNotYetSupportedError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


@pytest.mark.unit
def test_decide_raises_kind_not_yet_supported_for_bit_rot_checked() -> None:
    cmd = _good_command(kind="BitRotChecked")
    with pytest.raises(AttestationKindNotYetSupportedError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


# ---------- Evidence-outcome cross-validation ----------


@pytest.mark.unit
def test_decide_raises_when_match_outcome_has_no_computed_checksum() -> None:
    cmd = _good_command(outcome="Match", evidence_computed_checksum=None)
    with pytest.raises(InvalidAttestationEvidenceError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


@pytest.mark.unit
def test_decide_raises_when_mismatch_outcome_has_no_computed_checksum() -> None:
    cmd = _good_command(outcome="Mismatch", evidence_computed_checksum=None)
    with pytest.raises(InvalidAttestationEvidenceError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


@pytest.mark.unit
def test_decide_raises_when_unreachable_outcome_has_computed_checksum() -> None:
    cmd = _good_command(
        outcome="Unreachable",
        evidence_computed_checksum=_GOOD_SHA,
        evidence_error_detail="boom",
    )
    with pytest.raises(InvalidAttestationEvidenceError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


@pytest.mark.unit
def test_decide_raises_when_unreachable_outcome_has_no_error_detail() -> None:
    cmd = _good_command(
        outcome="Unreachable",
        evidence_computed_checksum=None,
        evidence_error_detail=None,
    )
    with pytest.raises(InvalidAttestationEvidenceError):
        record_attestation.decide(
            state=None,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )


# ---------- Cross-aggregate guards ----------


@pytest.mark.unit
def test_decide_raises_when_distribution_belongs_to_other_dataset() -> None:
    other_dataset_id = uuid4()
    cmd = _good_command()
    ctx = _context(
        distribution=_distribution(dataset_id=other_dataset_id),
    )
    with pytest.raises(AttestationDistributionDatasetMismatchError) as exc:
        record_attestation.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )
    assert exc.value.actual_dataset_id == other_dataset_id
    assert exc.value.expected_dataset_id == _DATASET_ID


@pytest.mark.unit
def test_decide_raises_when_match_evidence_differs_from_distribution_checksum() -> None:
    cmd = _good_command(evidence_computed_checksum=_OTHER_SHA)
    ctx = _context(distribution=_distribution(checksum_value=_GOOD_SHA))
    # Match with a non-canonical computed_checksum is a false-Match
    # bug; the belt-and-braces guard must catch it.
    with pytest.raises(AttestationChecksumEvidenceMismatchError) as exc:
        record_attestation.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )
    assert exc.value.canonical_checksum == _GOOD_SHA
    assert exc.value.evidence_checksum == _OTHER_SHA


@pytest.mark.unit
def test_decide_does_not_raise_for_mismatch_with_differing_computed_checksum() -> None:
    """Mismatch with computed != canonical is the legitimate fact-act
    of recording a Mismatch; the belt-and-braces guard ONLY fires on
    Match (false-Match is the downstream-visible failure mode)."""
    cmd = _good_command(outcome="Mismatch", evidence_computed_checksum=_OTHER_SHA)
    ctx = _context(distribution=_distribution(checksum_value=_GOOD_SHA))
    events = record_attestation.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=uuid4(),
        attested_by=_PRINCIPAL,
    )
    assert events[0].outcome == "Mismatch"


# ---------- Strict-not-idempotent ----------


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_not_none() -> None:
    existing_id = uuid4()
    cmd = _good_command()
    existing = _existing(existing_id)
    with pytest.raises(AttestationAlreadyExistsError) as exc:
        record_attestation.decide(
            state=existing,
            command=cmd,
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
            attested_by=_PRINCIPAL,
        )
    assert exc.value.attestation_id == existing_id


# ---------- Purity ----------


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cmd = _good_command()
    ctx = _context()
    first = record_attestation.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        attested_by=_PRINCIPAL,
    )
    second = record_attestation.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        attested_by=_PRINCIPAL,
    )
    assert first == second
