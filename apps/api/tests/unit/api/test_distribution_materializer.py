"""Unit tests for `DistributionMaterializer` (leg B of stage-then-reconstruct).

Exercises the sequence transfer -> register_distribution -> record_attestation
against the in-memory TransferPort double and fake Data BC handlers: nothing
here stands up a Kernel or touches an event store.
"""

from uuid import UUID, uuid4

import pytest

from cora.api._distribution_materializer import DistributionMaterializer
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.adapters.in_memory_transfer_port import InMemoryTransferPort
from cora.operation.ports.transfer_port import TransferProgress, TransferRequest, TransferState

_DATASET_ID = uuid4()
_SUPPLY_ID = uuid4()
_DISTRIBUTION_ID = uuid4()
_ATTESTATION_ID = uuid4()
_PRINCIPAL_ID = uuid4()
_CORRELATION_ID = uuid4()

_TRANSFER = TransferRequest(
    source="tomdet:/local1/2BM/2026-03-Pickering-1008279/scan_001.h5",
    destination="tomo1:/data2/2BM/2026-03-Pickering-1008279/scan_001.h5",
)
_REGISTRATION = RegisterDistribution(
    dataset_id=_DATASET_ID,
    supply_id=_SUPPLY_ID,
    uri="file:///data2/2BM/2026-03-Pickering-1008279/scan_001.h5",
    checksum_algorithm="sha256",
    checksum_value="a" * 64,
    byte_size=4096,
    media_type="application/x-hdf5",
    access_protocol="POSIX",
)


class _FakeRegisterHandler:
    """Records each RegisterDistribution call; returns a fixed distribution id."""

    def __init__(self, distribution_id: UUID) -> None:
        self._distribution_id = distribution_id
        self.commands: list[RegisterDistribution] = []
        self.principals: list[UUID] = []
        self.correlations: list[UUID] = []

    async def __call__(
        self,
        command: RegisterDistribution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        self.commands.append(command)
        self.principals.append(principal_id)
        self.correlations.append(correlation_id)
        return self._distribution_id


class _FakeAttestHandler:
    """Records each RecordAttestation call; returns a fixed attestation id."""

    def __init__(self, attestation_id: UUID) -> None:
        self._attestation_id = attestation_id
        self.commands: list[RecordAttestation] = []

    async def __call__(
        self,
        command: RecordAttestation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        self.commands.append(command)
        return self._attestation_id


def _materializer(
    port: InMemoryTransferPort, register: _FakeRegisterHandler, attest: _FakeAttestHandler
) -> DistributionMaterializer:
    return DistributionMaterializer(
        transfer_port=port, register_distribution=register, record_attestation=attest
    )


async def _materialize(
    port: InMemoryTransferPort, register: _FakeRegisterHandler, attest: _FakeAttestHandler
):
    return await _materializer(port, register, attest).materialize(
        _TRANSFER,
        _REGISTRATION,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_successful_move_registers_then_attests_and_reports_materialized() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(TransferState.SUCCEEDED)
    register = _FakeRegisterHandler(_DISTRIBUTION_ID)
    attest = _FakeAttestHandler(_ATTESTATION_ID)

    outcome = await _materialize(port, register, attest)

    assert outcome.materialized is True
    assert outcome.transfer_state is TransferState.SUCCEEDED
    assert outcome.distribution_id == _DISTRIBUTION_ID
    assert outcome.attestation_id == _ATTESTATION_ID
    assert register.commands == [_REGISTRATION]


@pytest.mark.unit
async def test_attestation_is_built_from_the_dataset_and_new_distribution_id() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(TransferState.SUCCEEDED)
    register = _FakeRegisterHandler(_DISTRIBUTION_ID)
    attest = _FakeAttestHandler(_ATTESTATION_ID)

    await _materialize(port, register, attest)

    assert attest.commands == [
        RecordAttestation(
            dataset_id=_DATASET_ID,
            distribution_id=_DISTRIBUTION_ID,
            kind="ChecksumVerified",
        )
    ]


@pytest.mark.unit
async def test_failed_move_skips_register_and_attest() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(TransferState.FAILED, files_failed=3, detail="3 files unreadable")
    register = _FakeRegisterHandler(_DISTRIBUTION_ID)
    attest = _FakeAttestHandler(_ATTESTATION_ID)

    outcome = await _materialize(port, register, attest)

    assert outcome.materialized is False
    assert outcome.transfer_state is TransferState.FAILED
    assert outcome.distribution_id is None
    assert outcome.attestation_id is None
    assert outcome.transfer_detail == "3 files unreadable"
    assert register.commands == []
    assert attest.commands == []


@pytest.mark.unit
async def test_move_waits_through_a_non_terminal_suspended_then_materializes() -> None:
    port = InMemoryTransferPort()
    port.set_next_progression(
        (
            TransferProgress(state=TransferState.ACTIVE),
            TransferProgress(state=TransferState.SUSPENDED, detail="credential expired"),
            TransferProgress(state=TransferState.ACTIVE),
            TransferProgress(state=TransferState.SUCCEEDED),
        )
    )
    register = _FakeRegisterHandler(_DISTRIBUTION_ID)
    attest = _FakeAttestHandler(_ATTESTATION_ID)

    outcome = await _materialize(port, register, attest)

    assert outcome.materialized is True
    assert len(register.commands) == 1


@pytest.mark.unit
async def test_threads_principal_and_correlation_into_the_handlers() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(TransferState.SUCCEEDED)
    register = _FakeRegisterHandler(_DISTRIBUTION_ID)
    attest = _FakeAttestHandler(_ATTESTATION_ID)

    await _materialize(port, register, attest)

    assert register.principals == [_PRINCIPAL_ID]
    assert register.correlations == [_CORRELATION_ID]
