"""Property-based tests for `register_distribution.decide`.

Universal claims across generated inputs:

  - state=None + valid command + matching context emits a single
    DistributionRegistered carrying the injected ids / now / trimmed
    URI + closed-enum AccessProtocol.
  - state=Distribution always raises DistributionAlreadyExistsError.
  - context.supply.kind != "Storage" always raises
    DistributionCannotRegisterOnNonStorageSupplyError.
  - context.dataset.status == DISCARDED always raises
    DistributionCannotRegisterOnDiscardedDatasetError.
  - command.byte_size != dataset.byte_size always raises
    DistributionByteSizeMismatchError.
  - Pure: same (state, command, context, now, new_id, registered_by)
    returns the same events.

URI-scheme coverage NOT duplicated here: the closest sibling PBT
(DatasetUri) covers the urlparse + blocklist + length surface; we
constrain inputs to a small URI shape and rely on DatasetUri's PBT
for the universal scheme/length claims, per
[[feedback-pbt-check-existing-tests]] + project-data-distribution-design
W12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
    AccessProtocol,
    DistributionAlreadyExistsError,
    DistributionByteSizeMismatchError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionRegistered,
    DistributionStatus,
    DistributionUri,
)
from cora.data.aggregates.distribution.state import Distribution
from cora.data.features import register_distribution
from cora.data.features.register_distribution import (
    DistributionRegistrationContext,
    RegisterDistribution,
)
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH

# Restricted URI shape: keep within DistributionUri validation (scheme
# present, non-empty path, no blocked scheme). DatasetUri PBT covers
# the universal urlparse + blocklist + length claims; we focus here on
# the Distribution-specific decider properties.
_URI_PATH = st.from_regex(r"\A[a-z0-9\-_/]{1,40}\Z", fullmatch=True)
_PROTOCOL = st.sampled_from(list(AccessProtocol))
_BYTE_SIZE = st.integers(min_value=0, max_value=10_000_000)
_NON_STORAGE_KIND = st.sampled_from(["Consumable", "Sample", "Detector", "Reagent"])
_NON_DISCARDED_STATUS = st.sampled_from(
    [s for s in DatasetStatus if s is not DatasetStatus.DISCARDED]
)


def _dataset(
    dataset_id: UUID,
    *,
    byte_size: int,
    status: DatasetStatus,
) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://bucket/seed"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=byte_size,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


def _supply(supply_id: UUID, *, kind: str = "Storage") -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=supply_id,
        kind=kind,
        name="store",
        status="Available",
        facility_code="aps",
    )


def _existing(distribution_id: UUID, now: datetime) -> Distribution:
    return Distribution(
        id=distribution_id,
        dataset_id=distribution_id,  # arbitrary
        supply_id=distribution_id,
        uri=DistributionUri("s3://existing/d.h5"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        access_protocol=AccessProtocol.S3,
        registered_at=now,
        registered_by=ActorId(distribution_id),
        status=DistributionStatus.REGISTERED,
    )


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    supply_id=st.uuids(),
    uri_path=_URI_PATH,
    protocol=_PROTOCOL,
    byte_size=_BYTE_SIZE,
    now=aware_datetimes(),
    new_id=st.uuids(),
    registered_by=st.uuids(),
)
def test_register_distribution_happy_path_emits_one_event(
    dataset_id: UUID,
    supply_id: UUID,
    uri_path: str,
    protocol: AccessProtocol,
    byte_size: int,
    now: datetime,
    new_id: UUID,
    registered_by: UUID,
) -> None:
    """Valid inputs + matching context -> one DistributionRegistered."""
    cmd = RegisterDistribution(
        dataset_id=dataset_id,
        supply_id=supply_id,
        uri=f"s3://bucket/{uri_path}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=byte_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol=protocol.value,
    )
    ctx = DistributionRegistrationContext(
        dataset=_dataset(dataset_id, byte_size=byte_size, status=DatasetStatus.REGISTERED),
        supply=_supply(supply_id),
    )
    events = register_distribution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=now,
        new_id=new_id,
        registered_by=ActorId(registered_by),
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, DistributionRegistered)
    assert event.distribution_id == new_id
    assert event.dataset_id == dataset_id
    assert event.supply_id == supply_id
    assert event.byte_size == byte_size
    assert event.access_protocol == protocol.value
    assert event.occurred_at == now
    assert event.registered_by == ActorId(registered_by)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    dataset_id=st.uuids(),
    supply_id=st.uuids(),
    uri_path=_URI_PATH,
    protocol=_PROTOCOL,
    byte_size=_BYTE_SIZE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_distribution_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    dataset_id: UUID,
    supply_id: UUID,
    uri_path: str,
    protocol: AccessProtocol,
    byte_size: int,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state -> DistributionAlreadyExistsError, regardless of command."""
    cmd = RegisterDistribution(
        dataset_id=dataset_id,
        supply_id=supply_id,
        uri=f"s3://bucket/{uri_path}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=byte_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol=protocol.value,
    )
    ctx = DistributionRegistrationContext(
        dataset=_dataset(dataset_id, byte_size=byte_size, status=DatasetStatus.REGISTERED),
        supply=_supply(supply_id),
    )
    existing = _existing(existing_id, now)
    with pytest.raises(DistributionAlreadyExistsError) as exc:
        register_distribution.decide(
            state=existing,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            registered_by=ActorId(new_id),
        )
    assert exc.value.distribution_id == existing_id


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    supply_id=st.uuids(),
    uri_path=_URI_PATH,
    protocol=_PROTOCOL,
    byte_size=_BYTE_SIZE,
    non_storage_kind=_NON_STORAGE_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_distribution_non_storage_kind_always_raises(
    dataset_id: UUID,
    supply_id: UUID,
    uri_path: str,
    protocol: AccessProtocol,
    byte_size: int,
    non_storage_kind: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any context.supply.kind != 'Storage' -> reject."""
    cmd = RegisterDistribution(
        dataset_id=dataset_id,
        supply_id=supply_id,
        uri=f"s3://bucket/{uri_path}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=byte_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol=protocol.value,
    )
    ctx = DistributionRegistrationContext(
        dataset=_dataset(dataset_id, byte_size=byte_size, status=DatasetStatus.REGISTERED),
        supply=_supply(supply_id, kind=non_storage_kind),
    )
    with pytest.raises(DistributionCannotRegisterOnNonStorageSupplyError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            registered_by=ActorId(new_id),
        )


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    supply_id=st.uuids(),
    uri_path=_URI_PATH,
    protocol=_PROTOCOL,
    byte_size=_BYTE_SIZE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_distribution_discarded_dataset_always_raises(
    dataset_id: UUID,
    supply_id: UUID,
    uri_path: str,
    protocol: AccessProtocol,
    byte_size: int,
    now: datetime,
    new_id: UUID,
) -> None:
    """Discarded parent Dataset -> reject."""
    cmd = RegisterDistribution(
        dataset_id=dataset_id,
        supply_id=supply_id,
        uri=f"s3://bucket/{uri_path}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=byte_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol=protocol.value,
    )
    ctx = DistributionRegistrationContext(
        dataset=_dataset(dataset_id, byte_size=byte_size, status=DatasetStatus.DISCARDED),
        supply=_supply(supply_id),
    )
    with pytest.raises(DistributionCannotRegisterOnDiscardedDatasetError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            registered_by=ActorId(new_id),
        )


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    supply_id=st.uuids(),
    uri_path=_URI_PATH,
    protocol=_PROTOCOL,
    cmd_size=st.integers(min_value=0, max_value=10_000),
    dataset_size=st.integers(min_value=0, max_value=10_000),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_distribution_byte_size_mismatch_always_raises(
    dataset_id: UUID,
    supply_id: UUID,
    uri_path: str,
    protocol: AccessProtocol,
    cmd_size: int,
    dataset_size: int,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any cmd_size != dataset_size pair -> reject."""
    if cmd_size == dataset_size:
        return  # not the property under test
    cmd = RegisterDistribution(
        dataset_id=dataset_id,
        supply_id=supply_id,
        uri=f"s3://bucket/{uri_path}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=cmd_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol=protocol.value,
    )
    ctx = DistributionRegistrationContext(
        dataset=_dataset(dataset_id, byte_size=dataset_size, status=DatasetStatus.REGISTERED),
        supply=_supply(supply_id),
    )
    with pytest.raises(DistributionByteSizeMismatchError):
        register_distribution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            registered_by=ActorId(new_id),
        )


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    supply_id=st.uuids(),
    uri_path=_URI_PATH,
    protocol=_PROTOCOL,
    byte_size=_BYTE_SIZE,
    now=aware_datetimes(),
    new_id=st.uuids(),
    registered_by=st.uuids(),
)
def test_register_distribution_is_pure_same_input_same_output(
    dataset_id: UUID,
    supply_id: UUID,
    uri_path: str,
    protocol: AccessProtocol,
    byte_size: int,
    now: datetime,
    new_id: UUID,
    registered_by: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    cmd = RegisterDistribution(
        dataset_id=dataset_id,
        supply_id=supply_id,
        uri=f"s3://bucket/{uri_path}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=byte_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol=protocol.value,
    )
    ctx = DistributionRegistrationContext(
        dataset=_dataset(dataset_id, byte_size=byte_size, status=DatasetStatus.REGISTERED),
        supply=_supply(supply_id),
    )
    first = register_distribution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=now,
        new_id=new_id,
        registered_by=ActorId(registered_by),
    )
    second = register_distribution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=now,
        new_id=new_id,
        registered_by=ActorId(registered_by),
    )
    assert first == second
