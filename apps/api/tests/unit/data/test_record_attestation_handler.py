"""Unit tests for the ``record_attestation`` application handler.

The handler is verifier-port-driven: it dispatches on the Distribution URI
scheme to a ChecksumVerifier, walks the bytes, and records the computed
outcome. These tests inject the in-module verifier stubs via a
``deps.data.checksum_verifiers`` map (the BC-local adapter namespace
``wire_data`` would otherwise build) so no real I/O runs.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.attestation import (
    AttestationDistributionNotFoundError,
    AttestationKindNotYetSupportedError,
    AttestationKindRequiresDistributionError,
    AttestationTreeChecksumNotYetSupportedError,
)
from cora.data.aggregates.dataset import DatasetNotFoundError
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
)
from cora.data.aggregates.dataset.events import (
    event_type_name as dataset_event_type_name,
)
from cora.data.aggregates.dataset.events import (
    to_payload as dataset_to_payload,
)
from cora.data.aggregates.distribution.events import (
    DistributionRegistered,
)
from cora.data.aggregates.distribution.events import (
    event_type_name as distribution_event_type_name,
)
from cora.data.aggregates.distribution.events import (
    to_payload as distribution_to_payload,
)
from cora.data.features import record_attestation
from cora.data.features.record_attestation import RecordAttestation
from cora.data.ports.checksum_verifier import (
    AlwaysMatchingChecksumVerifier,
    AlwaysMismatchingChecksumVerifier,
    AlwaysUnreachableChecksumVerifier,
    ChecksumVerifier,
    ChecksumVerifierUnsupportedSchemeError,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA = "a" * 64
_OTHER_SHA = "b" * 64
_MISMATCH_SHA = "f" * 64  # AlwaysMismatchingChecksumVerifier's fixed digest
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ATTESTATION_ID = UUID("01900000-0000-7000-8000-00000000a771")
_REG_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a772")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da7a")
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000d1571")
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005519")

_HTTPS_URI = "https://store.example/data/k.h5"


def _good_command(**overrides: object) -> RecordAttestation:
    base: dict[str, object] = {
        "dataset_id": _DATASET_ID,
        "distribution_id": _DISTRIBUTION_ID,
        "kind": "ChecksumVerified",
    }
    base.update(overrides)
    return RecordAttestation(**base)  # type: ignore[arg-type]


def _bind(
    deps: Kernel,
    *,
    verifier: ChecksumVerifier | None = None,
    scheme: str = "https",
) -> record_attestation.Handler:
    """Attach a stub verifier map onto deps.data and bind the handler.

    A ``None`` verifier installs an empty map (every scheme unsupported).
    """
    verifiers: dict[str, ChecksumVerifier] = {} if verifier is None else {scheme: verifier}
    object.__setattr__(deps, "data", SimpleNamespace(checksum_verifiers=verifiers))
    return record_attestation.bind(deps)


async def _seed_dataset(
    store: InMemoryEventStore,
    dataset_id: UUID = _DATASET_ID,
    *,
    checksum_value: str = _GOOD_SHA,
    byte_size: int = 1024,
) -> None:
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="seed",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=checksum_value,
        byte_size=byte_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    new_event = to_new_event(
        event_type=dataset_event_type_name(event),
        payload=dataset_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDataset",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Dataset", stream_id=dataset_id, expected_version=0, events=[new_event]
    )


async def _seed_distribution(
    store: InMemoryEventStore,
    distribution_id: UUID = _DISTRIBUTION_ID,
    *,
    dataset_id: UUID = _DATASET_ID,
    checksum_value: str = _GOOD_SHA,
    checksum_algorithm: str = "sha256",
    uri: str = _HTTPS_URI,
    access_protocol: str = "HTTPS",
) -> None:
    event = DistributionRegistered(
        distribution_id=distribution_id,
        dataset_id=dataset_id,
        supply_id=_SUPPLY_ID,
        uri=uri,
        checksum_algorithm=checksum_algorithm,
        checksum_value=checksum_value,
        byte_size=1024,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol=access_protocol,
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    new_event = to_new_event(
        event_type=distribution_event_type_name(event),
        payload=distribution_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDistribution",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Distribution",
        stream_id=distribution_id,
        expected_version=0,
        events=[new_event],
    )


# ---------- Happy paths (verifier-computed outcome) ----------


@pytest.mark.unit
async def test_handler_returns_new_attestation_id_on_match() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    attestation_id = await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert attestation_id == _ATTESTATION_ID


@pytest.mark.unit
async def test_handler_records_computed_match_payload() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Attestation", _ATTESTATION_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["AttestationRecorded"]
    recorded = events[0]
    assert recorded.event_id == _REG_EVENT_ID
    assert recorded.metadata == {"command": "RecordAttestation"}
    payload = recorded.payload
    assert payload["attestation_id"] == str(_ATTESTATION_ID)
    assert payload["dataset_id"] == str(_DATASET_ID)
    assert payload["distribution_id"] == str(_DISTRIBUTION_ID)
    assert payload["kind"] == "ChecksumVerified"
    assert payload["outcome"] == "Match"
    assert payload["evidence"]["algorithm"] == "sha256"
    # The computed digest is CORA's, sourced from the verifier (here the
    # AlwaysMatching stub returns the Distribution's canonical checksum).
    assert payload["evidence"]["value"] == _GOOD_SHA
    assert payload["evidence"]["verifier_supply_id"] == str(_SUPPLY_ID)
    # verifier_kind records WHICH adapter computed the digest (the stub here).
    assert payload["evidence"]["verifier_kind"] == "AlwaysMatching"
    # attested_by is the caller (the operator/agent who asked CORA to verify).
    assert payload["attested_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_handler_records_mismatch_when_verifier_disagrees() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await _bind(deps, verifier=AlwaysMismatchingChecksumVerifier())(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    payload = events[0].payload
    assert payload["outcome"] == "Mismatch"
    assert payload["evidence"]["value"] == _MISMATCH_SHA


@pytest.mark.unit
async def test_handler_records_unreachable_when_verifier_cannot_walk() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    verifier = AlwaysUnreachableChecksumVerifier(error_detail="HEAD 503")
    await _bind(deps, verifier=verifier)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    payload = events[0].payload
    assert payload["outcome"] == "Unreachable"
    assert payload["evidence"]["value"] is None
    assert payload["evidence"]["error_detail"] == "HEAD 503"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    assert events[0].causation_id == causation


# ---------- Scheme dispatch ----------


@pytest.mark.unit
async def test_handler_raises_unsupported_scheme_when_no_verifier_for_uri() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store, uri="globus://endpoint/data/k.h5", access_protocol="Globus")
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    # Only an https verifier is configured; a globus:// Distribution has none.
    with pytest.raises(ChecksumVerifierUnsupportedSchemeError) as exc:
        await _bind(deps, verifier=AlwaysMatchingChecksumVerifier(), scheme="https")(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.scheme == "globus"
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    assert events == []


@pytest.mark.unit
async def test_handler_refuses_tree_checksum_distribution() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store, checksum_algorithm="sha256-tree")
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(AttestationTreeChecksumNotYetSupportedError):
        await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    assert events == []


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(
        ids=[_ATTESTATION_ID, _REG_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    with pytest.raises(UnauthorizedError):
        await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    assert events == []


# ---------- Handler-tier kind-not-yet-supported guard ----------


@pytest.mark.unit
async def test_handler_raises_kind_not_yet_supported_before_loading_dataset() -> None:
    store = InMemoryEventStore()
    # Intentionally do NOT seed the Dataset: the kind guard must fire
    # before the Dataset pre-load to avoid information leakage.
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(AttestationKindNotYetSupportedError):
        await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
            _good_command(kind="FormatValidated"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Cross-aggregate validation ----------


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_when_dataset_missing() -> None:
    store = InMemoryEventStore()
    await _seed_distribution(store, dataset_id=_DATASET_ID)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    missing = uuid4()
    with pytest.raises(DatasetNotFoundError):
        await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
            _good_command(dataset_id=missing),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_requires_distribution_when_id_missing() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(AttestationKindRequiresDistributionError):
        await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
            _good_command(distribution_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_distribution_not_found_when_missing() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    # NOTE: no seed_distribution call.
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(AttestationDistributionNotFoundError):
        await _bind(deps, verifier=AlwaysMatchingChecksumVerifier())(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_data_includes_record_attestation() -> None:
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.record_attestation)
