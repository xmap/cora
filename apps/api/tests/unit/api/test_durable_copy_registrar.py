"""Unit tests for `DigestingDurableCopyRegistrar`.

Real `InMemoryEventStore` throughout (not a mock): this registrar's
whole job is establishing idempotence from the WRITE model, so the
write model has to be real for a test of it to mean anything. Two
tests (`..._with_bytes_disagreeing_with_the_dataset_is_refused` and its
matching-file sibling) go one step further and wire a real
`PosixChecksumAdapter` over a real temp file rather than a configured
stub, for the reason `PosixChecksumAdapter`'s own docstring on the
independent-check principle gives: a stub that hands back whatever the
test wants would let the exact bug this pair exists to catch (sourcing
`checksum_value` / `checksum_algorithm` / `byte_size` from `dataset`
instead of the computed digest) hide one level up.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from cora.api._durable_copy_registrar import DigestingDurableCopyRegistrar
from cora.api._durable_distribution_driver import (
    DurableCopyAlreadyRegistered,
    DurableCopyRegistered,
    DurableCopyRegisterRefused,
    DurableCopyRegisterUnauthorized,
)
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.aggregates.dataset.events import DatasetRegistered
from cora.data.aggregates.dataset.events import event_type_name as dataset_event_type_name
from cora.data.aggregates.dataset.events import to_payload as dataset_to_payload
from cora.data.aggregates.dataset.state import DatasetChecksum, DatasetEncoding
from cora.data.aggregates.distribution.events import DistributionDiscarded
from cora.data.aggregates.distribution.events import (
    event_type_name as distribution_event_type_name,
)
from cora.data.aggregates.distribution.events import to_payload as distribution_to_payload
from cora.data.ports.checksum_computer import ChecksumComputationResult, ComputedChecksum
from cora.data.ports.checksum_verifier import Unreachable
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import AllowAllAuthorize, ConcurrencyError, FakeClock
from cora.infrastructure.ports.id_generator import FixedIdGenerator
from cora.infrastructure.ports.supply_lookup import (
    SingleSupplyLookup,
    SupplyLookupResult,
    UnknownSupplyLookup,
)
from cora.shared.identity import ActorId
from tests.unit._helpers import DenyAllAuthorize

if TYPE_CHECKING:
    from pathlib import Path

    from cora.infrastructure.ports.event_store import NewEvent, StreamAppend

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000da7a1")
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005519")
_LOCATOR = "cora-capture-path://tomdet/gdata-2bm/2026-08/abc123"
_GOOD_SHA256 = "a" * 64
_MEDIA_TYPE = "application/x-hdf5"


def _storage_supply() -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=_SUPPLY_ID,
        kind="Storage",
        name="durable-tier",
        status="Available",
        facility_code="aps",
    )


async def _seed_dataset(
    store: InMemoryEventStore,
    *,
    dataset_id: UUID = _DATASET_ID,
    checksum_algorithm: str = "sha256",
    checksum_value: str = _GOOD_SHA256,
    byte_size: int = 1024,
    media_type: str = _MEDIA_TYPE,
    conforms_to: frozenset[str] = frozenset(),
) -> None:
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="seed",
        uri="s3://b/k",
        checksum=DatasetChecksum(algorithm=checksum_algorithm, value=checksum_value),
        byte_size=byte_size,
        encoding=DatasetEncoding(media_type=media_type, conforms_to=conforms_to),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=ActorId(uuid4()),
    )
    new_event = to_new_event(
        event_type=dataset_event_type_name(event),
        payload=dataset_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDataset",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Dataset", stream_id=dataset_id, expected_version=0, events=[new_event]
    )


class _ConfiguredChecksumComputer:
    """Returns a fixed result for every call and records every call made."""

    kind = "Configured"

    def __init__(self, result: ChecksumComputationResult) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def compute(self, *, locator_uri: str, supply_id: UUID) -> ChecksumComputationResult:
        self.calls.append({"locator_uri": locator_uri, "supply_id": supply_id})
        return self._result


class _NeverCalledChecksumComputer:
    """Fails the test if `compute` is ever invoked, proving the caller
    checked idempotence BEFORE digesting."""

    kind = "NeverCalled"

    async def compute(self, *, locator_uri: str, supply_id: UUID) -> ChecksumComputationResult:
        raise AssertionError("compute must not be called before idempotence is established")


def _registrar(
    *,
    store: InMemoryEventStore,
    checksum_computer: Any,
    authz: Any | None = None,
    supply_lookup: Any | None = None,
    ids: list[UUID] | None = None,
) -> DigestingDurableCopyRegistrar:
    return DigestingDurableCopyRegistrar(
        event_store=store,
        authz=authz or AllowAllAuthorize(),
        supply_lookup=supply_lookup or SingleSupplyLookup(_storage_supply()),
        checksum_computer=checksum_computer,
        clock=FakeClock(at=_NOW),
        id_generator=FixedIdGenerator(ids or [uuid4() for _ in range(4)]),
    )


async def _register(
    registrar: DigestingDurableCopyRegistrar,
    *,
    dataset_id: UUID = _DATASET_ID,
    supply_id: UUID = _SUPPLY_ID,
    locator: str = _LOCATOR,
    durable_path: str = "/gdata/dm/2BM/2026-08-Haridy-1015116/data/scan_005.h5",
    access_protocol: str = "NFS",
    observed_modified_at: datetime = _NOW,
) -> Any:
    return await registrar.register(
        dataset_id=dataset_id,
        supply_id=supply_id,
        locator=locator,
        durable_path=durable_path,
        access_protocol=access_protocol,
        observed_modified_at=observed_modified_at,
    )


def _computed(
    *, algorithm: str = "sha256", value: str = _GOOD_SHA256, byte_size: int = 1024
) -> ComputedChecksum:
    return ComputedChecksum(
        algorithm=algorithm,
        value=value,
        byte_size=byte_size,
        mtime_ns=int(_NOW.timestamp() * 1_000_000_000),
    )


# ---------- Write-model idempotence / generation chain ----------


async def _discard(store: InMemoryEventStore, *, distribution_id: UUID, version: int) -> None:
    """Discard an existing Distribution directly (out of band, as an
    operator's `discard_distribution` call would)."""
    discard = DistributionDiscarded(
        distribution_id=distribution_id,
        reason="test discard",
        occurred_at=_NOW,
        discarded_by=ActorId(uuid4()),
    )
    await store.append(
        stream_type="Distribution",
        stream_id=distribution_id,
        expected_version=version,
        events=[
            to_new_event(
                event_type=distribution_event_type_name(discard),
                payload=distribution_to_payload(discard),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DiscardDistribution",
                correlation_id=uuid4(),
                principal_id=uuid4(),
            )
        ],
    )


async def test_register_on_an_empty_stream_registers_at_generation_zero() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    target_id = uuid4()
    registrar = _registrar(
        store=store, checksum_computer=_ConfiguredChecksumComputer(_computed()), ids=[target_id]
    )

    result = await _register(registrar)

    assert isinstance(result, DurableCopyRegistered)
    assert result.distribution_id != uuid4()  # a real id was minted
    events, version = await store.load("Distribution", result.distribution_id)
    assert version == 1
    assert events[0].event_type == "DistributionRegistered"


async def test_register_against_an_already_registered_generation_is_idempotent() -> None:
    """The idempotence check must fire BEFORE any digest: a
    `_NeverCalledChecksumComputer` proves the digest path is never
    reached when the write model already answers the question."""
    store = InMemoryEventStore()
    await _seed_dataset(store)
    # Derive generation-0's id the same way the registrar does, by
    # letting a first real registration happen, then repeating the call.
    first_registrar = _registrar(
        store=store, checksum_computer=_ConfiguredChecksumComputer(_computed())
    )
    first = await _register(first_registrar)
    assert isinstance(first, DurableCopyRegistered)

    second_registrar = _registrar(store=store, checksum_computer=_NeverCalledChecksumComputer())
    second = await _register(second_registrar)

    assert second == DurableCopyAlreadyRegistered(distribution_id=first.distribution_id)


async def test_register_advances_past_a_discarded_generation() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    first_registrar = _registrar(
        store=store, checksum_computer=_ConfiguredChecksumComputer(_computed())
    )
    first = await _register(first_registrar)
    assert isinstance(first, DurableCopyRegistered)
    await _discard(store, distribution_id=first.distribution_id, version=1)

    second_registrar = _registrar(
        store=store, checksum_computer=_ConfiguredChecksumComputer(_computed())
    )
    second = await _register(second_registrar)

    assert isinstance(second, DurableCopyRegistered)
    assert second.distribution_id != first.distribution_id


async def test_register_refuses_once_every_generation_is_discarded_without_digesting() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    # Walk and discard four generations in a row.
    for _ in range(4):
        result = await _register(
            _registrar(store=store, checksum_computer=_ConfiguredChecksumComputer(_computed()))
        )
        assert isinstance(result, DurableCopyRegistered)
        await _discard(store, distribution_id=result.distribution_id, version=1)

    final_registrar = _registrar(store=store, checksum_computer=_NeverCalledChecksumComputer())
    final = await _register(final_registrar)

    assert isinstance(final, DurableCopyRegisterRefused)
    assert "discarded" in final.detail


# ---------- Authorization ----------


async def test_register_denied_returns_unauthorized_without_digesting() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    registrar = _registrar(
        store=store, checksum_computer=_NeverCalledChecksumComputer(), authz=DenyAllAuthorize()
    )

    result = await _register(registrar)

    assert result == DurableCopyRegisterUnauthorized()


# ---------- Cross-reference loads ----------


async def test_register_missing_dataset_is_refused() -> None:
    store = InMemoryEventStore()  # no dataset seeded
    registrar = _registrar(store=store, checksum_computer=_NeverCalledChecksumComputer())

    result = await _register(registrar)

    assert isinstance(result, DurableCopyRegisterRefused)


async def test_register_missing_supply_is_refused() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    registrar = _registrar(
        store=store,
        checksum_computer=_NeverCalledChecksumComputer(),
        supply_lookup=UnknownSupplyLookup(),
    )

    result = await _register(registrar)

    assert isinstance(result, DurableCopyRegisterRefused)


# ---------- Digest failure ----------


async def test_register_unreachable_digest_refuses_with_a_fixed_literal(tmp_path: Path) -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    secret_fragment = "Smith-1015116"
    computer = _ConfiguredChecksumComputer(
        Unreachable(error_detail=f"read failed: /gdata/dm/2BM/2026-08-{secret_fragment}/x.h5")
    )
    registrar = _registrar(store=store, checksum_computer=computer)

    result = await _register(registrar)

    assert isinstance(result, DurableCopyRegisterRefused)
    assert secret_fragment not in result.detail
    _ = tmp_path


async def test_register_mtime_disagreement_is_refused() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    disagreeing_mtime_ns = int((_NOW.timestamp() + 3600) * 1_000_000_000)
    computer = _ConfiguredChecksumComputer(
        ComputedChecksum(
            algorithm="sha256", value=_GOOD_SHA256, byte_size=1024, mtime_ns=disagreeing_mtime_ns
        )
    )
    registrar = _registrar(store=store, checksum_computer=computer)

    result = await _register(registrar, observed_modified_at=_NOW)

    assert isinstance(result, DurableCopyRegisterRefused)
    events, _ = await store.load("Distribution", uuid4())
    assert events == []


# ---------- The independence trap: real bytes, real file, real mismatch ----------


async def test_a_durable_copy_whose_bytes_disagree_with_the_dataset_is_refused(
    tmp_path: Path,
) -> None:
    """The mutation-tested case: `checksum_value`, `checksum_algorithm`
    and `byte_size` must all come from the COMPUTED digest, never from
    `dataset`. A real `PosixChecksumAdapter` digesting a real file whose
    true bytes disagree with the seeded Dataset proves it: sourcing any
    one of the three from `dataset` instead would make this pass for
    the wrong reason (the check would agree with itself)."""
    store = InMemoryEventStore()
    await _seed_dataset(store, checksum_value=_GOOD_SHA256, byte_size=1024)
    real_file = tmp_path / "durable" / "scan_005.h5"
    real_file.parent.mkdir(parents=True)
    real_file.write_bytes(b"these are not the seeded dataset's bytes")
    adapter = PosixChecksumAdapter(allowed_roots=(str(tmp_path),))
    registrar = _registrar(store=store, checksum_computer=adapter)

    result = await _register(
        registrar,
        durable_path=str(real_file),
        observed_modified_at=datetime.fromtimestamp(real_file.stat().st_mtime, tz=UTC),
    )

    assert isinstance(result, DurableCopyRegisterRefused)
    # No Distribution was appended anywhere: the stream this would have
    # landed on (generation 0 of this triple) must still be empty.
    from cora.api import _durable_copy_registrar as registrar_module

    target_id = registrar_module._derive_candidate_distribution_id(  # pyright: ignore[reportPrivateUsage]
        dataset_id=_DATASET_ID, supply_id=_SUPPLY_ID, locator=_LOCATOR, generation=0
    )
    events, version = await store.load("Distribution", target_id)
    assert events == []
    assert version == 0


async def test_a_durable_copy_whose_algorithm_disagrees_with_the_dataset_is_refused(
    tmp_path: Path,
) -> None:
    """Isolates the `checksum_algorithm` field specifically: the VALUE
    and BYTE_SIZE below match the real file exactly, so only sourcing
    `checksum_algorithm` from `computed` (never `dataset`) can make this
    refuse. `PosixChecksumAdapter` always computes `sha256`; seeding the
    Dataset as `sha256-tree` with the same real digest value isolates
    the one field this test exists to pin."""
    import hashlib

    payload = b"bytes whose sha256 digest is what we seed below"
    digest = hashlib.sha256(payload).hexdigest()
    store = InMemoryEventStore()
    await _seed_dataset(
        store, checksum_algorithm="sha256-tree", checksum_value=digest, byte_size=len(payload)
    )
    real_file = tmp_path / "durable" / "scan_005.h5"
    real_file.parent.mkdir(parents=True)
    real_file.write_bytes(payload)
    adapter = PosixChecksumAdapter(allowed_roots=(str(tmp_path),))
    registrar = _registrar(store=store, checksum_computer=adapter)

    result = await _register(
        registrar,
        durable_path=str(real_file),
        observed_modified_at=datetime.fromtimestamp(real_file.stat().st_mtime, tz=UTC),
    )

    assert isinstance(result, DurableCopyRegisterRefused)


async def test_a_durable_copy_whose_checksum_value_disagrees_with_the_dataset_is_refused(
    tmp_path: Path,
) -> None:
    """Isolates `checksum_value` specifically: ALGORITHM and BYTE_SIZE
    below match the real file exactly, so only sourcing `checksum_value`
    from `computed` (never `dataset`) can make this refuse."""
    payload = b"the real bytes this durable copy actually holds"
    store = InMemoryEventStore()
    await _seed_dataset(store, checksum_value="f" * 64, byte_size=len(payload))
    real_file = tmp_path / "durable" / "scan_005.h5"
    real_file.parent.mkdir(parents=True)
    real_file.write_bytes(payload)
    adapter = PosixChecksumAdapter(allowed_roots=(str(tmp_path),))
    registrar = _registrar(store=store, checksum_computer=adapter)

    result = await _register(
        registrar,
        durable_path=str(real_file),
        observed_modified_at=datetime.fromtimestamp(real_file.stat().st_mtime, tz=UTC),
    )

    assert isinstance(result, DurableCopyRegisterRefused)


async def test_a_durable_copy_whose_byte_size_disagrees_with_the_dataset_is_refused(
    tmp_path: Path,
) -> None:
    """Isolates `byte_size` specifically: ALGORITHM and VALUE below
    match the real file exactly, so only sourcing `byte_size` from
    `computed` (never `dataset`) can make this refuse."""
    import hashlib

    payload = b"the real bytes this durable copy actually holds, again"
    digest = hashlib.sha256(payload).hexdigest()
    store = InMemoryEventStore()
    await _seed_dataset(store, checksum_value=digest, byte_size=len(payload) + 1)
    real_file = tmp_path / "durable" / "scan_005.h5"
    real_file.parent.mkdir(parents=True)
    real_file.write_bytes(payload)
    adapter = PosixChecksumAdapter(allowed_roots=(str(tmp_path),))
    registrar = _registrar(store=store, checksum_computer=adapter)

    result = await _register(
        registrar,
        durable_path=str(real_file),
        observed_modified_at=datetime.fromtimestamp(real_file.stat().st_mtime, tz=UTC),
    )

    assert isinstance(result, DurableCopyRegisterRefused)


async def test_a_durable_copy_whose_bytes_match_the_dataset_is_registered(tmp_path: Path) -> None:
    """Sibling of the mismatch test above: without this, a registrar
    that refuses UNCONDITIONALLY would also pass the mismatch test."""
    import hashlib

    payload = b"these bytes match the seeded dataset exactly"
    digest = hashlib.sha256(payload).hexdigest()
    store = InMemoryEventStore()
    await _seed_dataset(store, checksum_value=digest, byte_size=len(payload))
    real_file = tmp_path / "durable" / "scan_005.h5"
    real_file.parent.mkdir(parents=True)
    real_file.write_bytes(payload)
    adapter = PosixChecksumAdapter(allowed_roots=(str(tmp_path),))
    registrar = _registrar(store=store, checksum_computer=adapter)

    result = await _register(
        registrar,
        durable_path=str(real_file),
        observed_modified_at=datetime.fromtimestamp(real_file.stat().st_mtime, tz=UTC),
    )

    assert isinstance(result, DurableCopyRegistered)
    events, version = await store.load("Distribution", result.distribution_id)
    assert version == 1
    assert events[0].payload["checksum"] == {"algorithm": "sha256", "value": digest}
    assert events[0].payload["byte_size"] == len(payload)


# ---------- encoding fields carried from dataset, unchecked by the decider ----------


async def test_register_success_carries_media_type_and_conforms_to_from_dataset() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(
        store,
        media_type="application/x-zarr",
        conforms_to=frozenset({"https://ngff.openmicroscopy.org/0.4/"}),
    )
    registrar = _registrar(store=store, checksum_computer=_ConfiguredChecksumComputer(_computed()))

    result = await _register(registrar)

    assert isinstance(result, DurableCopyRegistered)
    events, _ = await store.load("Distribution", result.distribution_id)
    assert events[0].payload["encoding"]["media_type"] == "application/x-zarr"
    assert events[0].payload["encoding"]["conforms_to"] == ["https://ngff.openmicroscopy.org/0.4/"]


# ---------- ConcurrencyError on append ----------


class _RacingEventStore:
    """Delegates `load` to a real store; `append` raises ConcurrencyError
    once, simulating a second writer winning the race to the same id."""

    def __init__(self, inner: InMemoryEventStore) -> None:
        self._inner = inner
        self._raised = False

    async def load(self, stream_type: str, stream_id: UUID) -> Any:
        return await self._inner.load(stream_type, stream_id)

    async def append(
        self, stream_type: str, stream_id: UUID, expected_version: int, events: list[NewEvent]
    ) -> int:
        if not self._raised:
            self._raised = True
            raise ConcurrencyError(stream_type, stream_id, expected_version, expected_version + 1)
        return await self._inner.append(stream_type, stream_id, expected_version, events)

    async def append_streams(
        self, streams: list[StreamAppend], *, conn: object | None = None
    ) -> dict[UUID, int]:
        return await self._inner.append_streams(streams, conn=conn)


async def test_register_concurrency_error_on_append_returns_already_registered() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    racing_store = _RacingEventStore(store)
    registrar = DigestingDurableCopyRegistrar(
        event_store=racing_store,  # type: ignore[arg-type]
        authz=AllowAllAuthorize(),
        supply_lookup=SingleSupplyLookup(_storage_supply()),
        checksum_computer=_ConfiguredChecksumComputer(_computed()),
        clock=FakeClock(at=_NOW),
        id_generator=FixedIdGenerator([uuid4()]),
    )

    result = await _register(registrar)

    assert isinstance(result, DurableCopyAlreadyRegistered)
