"""Unit tests for the `record_acquisition` slice's pure decider.

Genesis-style decider: state must be None (otherwise
AcquisitionAlreadyExistsError); shape VOs validate settings /
evidence / captured_at; the Capturing-affordance gate rejects an
Asset whose Family does not declare Capturing.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.acquisition import (
    AcquisitionAlreadyExistsError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionStatus,
    InvalidAcquisitionCapturedAtError,
    InvalidAcquisitionEvidenceError,
    InvalidAcquisitionSettingsError,
)
from cora.data.aggregates.acquisition.state import Acquisition
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetUri,
)
from cora.data.features import record_acquisition
from cora.data.features.record_acquisition import (
    AcquisitionRecordingContext,
    RecordAcquisition,
)
from cora.infrastructure.ports.asset_lookup import AssetLookupResult
from cora.run.aggregates.run import Run, RunName, RunStatus
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_CAPTURED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC)
_RECORDED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000d9"))
_DATASET_ID = uuid4()
_ASSET_ID = uuid4()
_NEW_ID = uuid4()


def _command(**overrides: object) -> RecordAcquisition:
    base: dict[str, object] = {
        "dataset_id": _DATASET_ID,
        "producing_asset_id": _ASSET_ID,
        "captured_at": _CAPTURED_AT,
        "producing_run_id": None,
        "settings": {"exposure_ms": 200},
        "evidence": {"frames": 1801},
    }
    base.update(overrides)
    return RecordAcquisition(**base)  # type: ignore[arg-type]


def _fake_dataset() -> Dataset:
    return Dataset(
        id=_DATASET_ID,
        name=DatasetName("recon.h5"),
        uri=DatasetUri("s3://b/recon.h5"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
    )


def _fake_asset(*, affordances: frozenset[str] = frozenset({"Capturing"})) -> AssetLookupResult:
    return AssetLookupResult(
        id=_ASSET_ID,
        name="Oryx Detector",
        tier="Device",
        lifecycle="Active",
        family_affordances=affordances,
    )


def _fake_run() -> Run:
    return Run(
        id=uuid4(),
        name=RunName("seed-run"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=RunStatus.RUNNING,
    )


def _context(
    *,
    asset: AssetLookupResult | None = None,
    run: Run | None = None,
) -> AcquisitionRecordingContext:
    return AcquisitionRecordingContext(
        dataset=_fake_dataset(),
        asset=asset if asset is not None else _fake_asset(),
        run=run,
    )


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_acquisition_recorded_on_valid_command() -> None:
    events = record_acquisition.decide(
        state=None,
        command=_command(),
        context=_context(),
        now=_NOW,
        new_id=_NEW_ID,
        recorded_by=_RECORDED_BY,
    )
    assert len(events) == 1
    event = events[0]
    assert event.acquisition_id == _NEW_ID
    assert event.dataset_id == _DATASET_ID
    assert event.producing_asset_id == _ASSET_ID
    assert event.producing_run_id is None
    assert event.captured_at == _CAPTURED_AT
    assert event.occurred_at == _NOW
    assert event.recorded_by == _RECORDED_BY
    assert event.settings == {"exposure_ms": 200}
    assert event.evidence == {"frames": 1801}


@pytest.mark.unit
def test_decide_emits_with_producing_run_id_when_set() -> None:
    run_id = uuid4()
    events = record_acquisition.decide(
        state=None,
        command=_command(producing_run_id=run_id),
        context=_context(run=_fake_run()),
        now=_NOW,
        new_id=_NEW_ID,
        recorded_by=_RECORDED_BY,
    )
    assert events[0].producing_run_id == run_id


@pytest.mark.unit
def test_decide_accepts_captured_at_far_in_past() -> None:
    """Backfills are legitimate: captured_at may precede now by days."""
    old = _NOW - timedelta(days=30)
    events = record_acquisition.decide(
        state=None,
        command=_command(captured_at=old),
        context=_context(),
        now=_NOW,
        new_id=_NEW_ID,
        recorded_by=_RECORDED_BY,
    )
    assert events[0].captured_at == old


# ---------- Rejections ----------


@pytest.mark.unit
def test_decide_raises_already_exists_on_non_none_state() -> None:
    existing = Acquisition(
        id=_NEW_ID,
        dataset_id=_DATASET_ID,
        producing_asset_id=_ASSET_ID,
        producing_run_id=None,
        captured_at=_CAPTURED_AT,
        settings={},
        evidence={},
        recorded_at=_NOW,
        recorded_by=_RECORDED_BY,
        status=AcquisitionStatus.RECORDED,
    )
    with pytest.raises(AcquisitionAlreadyExistsError) as exc:
        record_acquisition.decide(
            state=existing,
            command=_command(),
            context=_context(),
            now=_NOW,
            new_id=_NEW_ID,
            recorded_by=_RECORDED_BY,
        )
    assert exc.value.acquisition_id == _NEW_ID


@pytest.mark.unit
def test_decide_raises_missing_capturing_affordance() -> None:
    with pytest.raises(AcquisitionCannotRecordWithoutCapturingError) as exc:
        record_acquisition.decide(
            state=None,
            command=_command(),
            context=_context(asset=_fake_asset(affordances=frozenset({"Imageable"}))),
            now=_NOW,
            new_id=_NEW_ID,
            recorded_by=_RECORDED_BY,
        )
    assert exc.value.asset_id == _ASSET_ID


@pytest.mark.unit
def test_decide_raises_missing_capturing_affordance_on_empty_set() -> None:
    with pytest.raises(AcquisitionCannotRecordWithoutCapturingError):
        record_acquisition.decide(
            state=None,
            command=_command(),
            context=_context(asset=_fake_asset(affordances=frozenset[str]())),
            now=_NOW,
            new_id=_NEW_ID,
            recorded_by=_RECORDED_BY,
        )


@pytest.mark.unit
def test_decide_raises_on_future_captured_at_beyond_skew() -> None:
    future = _NOW + timedelta(minutes=5)
    with pytest.raises(InvalidAcquisitionCapturedAtError, match="future"):
        record_acquisition.decide(
            state=None,
            command=_command(captured_at=future),
            context=_context(),
            now=_NOW,
            new_id=_NEW_ID,
            recorded_by=_RECORDED_BY,
        )


@pytest.mark.unit
def test_decide_accepts_captured_at_within_skew_tolerance() -> None:
    """captured_at slightly ahead of now (within tolerance) is accepted."""
    slightly_ahead = _NOW + timedelta(seconds=30)
    events = record_acquisition.decide(
        state=None,
        command=_command(captured_at=slightly_ahead),
        context=_context(),
        now=_NOW,
        new_id=_NEW_ID,
        recorded_by=_RECORDED_BY,
    )
    assert events[0].captured_at == slightly_ahead


@pytest.mark.unit
def test_decide_raises_on_naive_captured_at() -> None:
    naive = datetime(2026, 6, 10, 9, 0, 0)  # intentional naive datetime (no tzinfo)
    with pytest.raises(InvalidAcquisitionCapturedAtError, match="timezone-aware"):
        record_acquisition.decide(
            state=None,
            command=_command(captured_at=naive),
            context=_context(),
            now=_NOW,
            new_id=_NEW_ID,
            recorded_by=_RECORDED_BY,
        )


@pytest.mark.unit
def test_decide_raises_on_malformed_settings() -> None:
    with pytest.raises(InvalidAcquisitionSettingsError):
        record_acquisition.decide(
            state=None,
            command=_command(settings={"bad": object()}),
            context=_context(),
            now=_NOW,
            new_id=_NEW_ID,
            recorded_by=_RECORDED_BY,
        )


@pytest.mark.unit
def test_decide_raises_on_malformed_evidence() -> None:
    with pytest.raises(InvalidAcquisitionEvidenceError):
        record_acquisition.decide(
            state=None,
            command=_command(evidence={"bad": object()}),
            context=_context(),
            now=_NOW,
            new_id=_NEW_ID,
            recorded_by=_RECORDED_BY,
        )
