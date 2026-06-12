"""Unit tests for the `register_distribution` slice's pure decider.

Genesis-style decider: state must be None (otherwise
DistributionAlreadyExistsError); reason VOs validate input; context
carries the parent Dataset + cross-BC SupplyLookupResult, both required
by the handler before the decider runs (per L17).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetStatus,
    DatasetUri,
)
from cora.data.aggregates.distribution import (
    DistributionAlreadyExistsError,
    DistributionByteSizeMismatchError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumMismatchError,
    DistributionStatus,
    DistributionUri,
    InvalidAccessProtocolError,
    InvalidDistributionByteSizeError,
    InvalidDistributionChecksumError,
    InvalidDistributionEncodingError,
    InvalidDistributionUriError,
)
from cora.data.aggregates.distribution.state import Distribution
from cora.data.features import register_distribution
from cora.data.features.register_distribution import (
    DistributionRegistrationContext,
    RegisterDistribution,
)
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_OTHER_SHA256 = "b" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000aa"))


def _good_command(**overrides: object) -> RegisterDistribution:
    base: dict[str, object] = {
        "dataset_id": UUID("01900000-0000-7000-8000-00000000d001"),
        "supply_id": UUID("01900000-0000-7000-8000-00000000571a"),
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "conforms_to": frozenset[str](),
        "access_protocol": "S3",
    }
    base.update(overrides)
    return RegisterDistribution(**base)  # type: ignore[arg-type]


def _dataset(
    dataset_id: UUID,
    *,
    checksum_value: str = _GOOD_SHA256,
    byte_size: int = 1024,
    status: DatasetStatus = DatasetStatus.REGISTERED,
) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed-dataset"),
        uri=DatasetUri("s3://bucket/seed"),
        checksum=DatasetChecksum(algorithm="sha256", value=checksum_value),
        byte_size=byte_size,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


def _supply(
    supply_id: UUID,
    *,
    kind: str = "Storage",
    status: str = "Available",
) -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=supply_id,
        kind=kind,
        name="primary-storage",
        status=status,
        facility_code="aps",
    )


def _good_context(cmd: RegisterDistribution) -> DistributionRegistrationContext:
    return DistributionRegistrationContext(
        dataset=_dataset(cmd.dataset_id),
        supply=_supply(cmd.supply_id),
    )


def _existing_distribution(distribution_id: UUID) -> Distribution:
    return Distribution(
        id=distribution_id,
        dataset_id=uuid4(),
        supply_id=uuid4(),
        uri=DistributionUri("s3://existing/d.h5"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        access_protocol=__import__(
            "cora.data.aggregates.distribution", fromlist=["AccessProtocol"]
        ).AccessProtocol.S3,
        registered_at=_NOW,
        registered_by=_REGISTERED_BY,
        status=DistributionStatus.REGISTERED,
    )


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_distribution_registered_with_all_fields() -> None:
    new_id = uuid4()
    cmd = _good_command()
    events = register_distribution.decide(
        state=None,
        command=cmd,
        context=_good_context(cmd),
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    assert len(events) == 1
    event = events[0]
    assert event.distribution_id == new_id
    assert event.dataset_id == cmd.dataset_id
    assert event.supply_id == cmd.supply_id
    assert event.uri == cmd.uri
    assert event.checksum_algorithm == "sha256"
    assert event.checksum_value == _GOOD_SHA256
    assert event.byte_size == 1024
    assert event.media_type == "application/x-hdf5"
    assert event.conforms_to == frozenset()
    assert event.access_protocol == "S3"
    assert event.occurred_at == _NOW
    assert event.registered_by == _REGISTERED_BY


@pytest.mark.unit
def test_decide_trims_uri_via_value_object() -> None:
    cmd = _good_command(uri="  s3://b/k.h5  ")
    events = register_distribution.decide(
        state=None,
        command=cmd,
        context=_good_context(cmd),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].uri == "s3://b/k.h5"


@pytest.mark.unit
def test_decide_accepts_zero_byte_size_when_dataset_is_also_zero() -> None:
    cmd = _good_command(byte_size=0)
    ctx = DistributionRegistrationContext(
        dataset=_dataset(cmd.dataset_id, byte_size=0),
        supply=_supply(cmd.supply_id),
    )
    events = register_distribution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].byte_size == 0


@pytest.mark.unit
def test_decide_passes_conforms_to_through() -> None:
    cmd = _good_command(conforms_to=frozenset({"https://manual.nexusformat.org/"}))
    events = register_distribution.decide(
        state=None,
        command=cmd,
        context=_good_context(cmd),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].conforms_to == frozenset({"https://manual.nexusformat.org/"})


@pytest.mark.unit
def test_decide_binds_against_decommissioned_supply() -> None:
    """Per L28: SupplyLookup returns rows in every lifecycle status;
    Distribution decider only gates on kind. A Decommissioned-storage
    Supply is a valid binding target (archival completeness)."""
    cmd = _good_command()
    ctx = DistributionRegistrationContext(
        dataset=_dataset(cmd.dataset_id),
        supply=_supply(cmd.supply_id, status="Decommissioned"),
    )
    events = register_distribution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert len(events) == 1


# ---------- Field validation (VO step 2) ----------


@pytest.mark.unit
def test_decide_raises_invalid_uri_for_missing_scheme() -> None:
    cmd = _good_command(uri="just-a-path")
    with pytest.raises(InvalidDistributionUriError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_checksum_for_md5() -> None:
    cmd = _good_command(checksum_algorithm="md5", checksum_value="d" * 32)
    with pytest.raises(InvalidDistributionChecksumError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_byte_size_for_negative() -> None:
    cmd = _good_command(byte_size=-1)
    with pytest.raises(InvalidDistributionByteSizeError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_encoding_for_empty_media_type() -> None:
    cmd = _good_command(media_type="")
    with pytest.raises(InvalidDistributionEncodingError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_access_protocol_for_unknown_value() -> None:
    """Defensive re-check per L17 step 3: in-process callers bypassing the
    Pydantic boundary surface as InvalidAccessProtocolError."""
    cmd = _good_command(access_protocol="FTP")
    with pytest.raises(InvalidAccessProtocolError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


# ---------- Cross-aggregate guards ----------


@pytest.mark.unit
def test_decide_raises_on_discarded_dataset() -> None:
    cmd = _good_command()
    ctx = DistributionRegistrationContext(
        dataset=_dataset(cmd.dataset_id, status=DatasetStatus.DISCARDED),
        supply=_supply(cmd.supply_id),
    )
    with pytest.raises(DistributionCannotRegisterOnDiscardedDatasetError) as exc:
        register_distribution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.dataset_id == cmd.dataset_id


@pytest.mark.unit
def test_decide_raises_on_non_storage_supply_kind() -> None:
    cmd = _good_command()
    ctx = DistributionRegistrationContext(
        dataset=_dataset(cmd.dataset_id),
        supply=_supply(cmd.supply_id, kind="Consumable"),
    )
    with pytest.raises(DistributionCannotRegisterOnNonStorageSupplyError) as exc:
        register_distribution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.supply_id == cmd.supply_id
    assert exc.value.actual_kind == "Consumable"


@pytest.mark.unit
def test_decide_raises_on_checksum_mismatch() -> None:
    cmd = _good_command(checksum_value=_OTHER_SHA256)
    ctx = DistributionRegistrationContext(
        dataset=_dataset(cmd.dataset_id, checksum_value=_GOOD_SHA256),
        supply=_supply(cmd.supply_id),
    )
    with pytest.raises(DistributionChecksumMismatchError) as exc:
        register_distribution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.expected_checksum == _GOOD_SHA256
    assert exc.value.actual_checksum == _OTHER_SHA256


@pytest.mark.unit
def test_decide_raises_on_byte_size_mismatch() -> None:
    cmd = _good_command(byte_size=2048)
    ctx = DistributionRegistrationContext(
        dataset=_dataset(cmd.dataset_id, byte_size=1024),
        supply=_supply(cmd.supply_id),
    )
    with pytest.raises(DistributionByteSizeMismatchError) as exc:
        register_distribution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.expected_byte_size == 1024
    assert exc.value.actual_byte_size == 2048


# ---------- Strict-not-idempotent ----------


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_not_none() -> None:
    existing_id = uuid4()
    cmd = _good_command()
    existing = _existing_distribution(existing_id)
    with pytest.raises(DistributionAlreadyExistsError) as exc:
        register_distribution.decide(
            state=existing,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.distribution_id == existing_id


# ---------- Purity ----------


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cmd = _good_command()
    ctx = _good_context(cmd)
    first = register_distribution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    second = register_distribution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    assert first == second
