"""Unit tests for `FdtTransferPort` against a fake transfer runner.

The adapter builds an `fdt.jar` client invocation from a `TransferRequest` and
maps the subprocess exit code into a `TransferState`. The runner is faked, so
nothing here launches a real process; live FDT behaviour is unverified.
"""

import pytest

from cora.operation.adapters.fdt_transfer_port import FdtTransferPort
from cora.operation.ports.transfer_port import (
    TransferEndpointUnreachableError,
    TransferPort,
    TransferRejectedError,
    TransferRequest,
    TransferState,
)

_SOURCE = "tomdet:/local1/2BM/2026-06/scan_001.h5"
_DESTINATION = "tomo1:/data2/2BM/2026-06"
_STAGE_IN = TransferRequest(source=_SOURCE, destination=_DESTINATION)


class _FakeRunner:
    """Records launched argv; replays a seeded exit-code sequence per move."""

    def __init__(self) -> None:
        self.started_argv: list[tuple[str, ...]] = []
        self.terminated: list[str] = []
        self._start_error: Exception | None = None
        self._sequences: list[list[int | None]] = []
        self._poll_state: dict[str, list[int | None]] = {}
        self._counter = 0

    def set_start_error(self, error: Exception) -> None:
        self._start_error = error

    def set_next_exit_sequence(self, sequence: list[int | None]) -> None:
        """Seed the exit-code sequence the next started move reports (one per poll).

        Each `poll` returns the next element, clamping on the last; None means
        still running. With nothing seeded a move polls as exit code 0 (success).
        """
        self._sequences.append(list(sequence))

    async def start(self, argv: tuple[str, ...]) -> str:
        if self._start_error is not None:
            raise self._start_error
        self.started_argv.append(argv)
        self._counter += 1
        token = f"fake-{self._counter}"
        self._poll_state[token] = self._sequences.pop(0) if self._sequences else [0]
        return token

    async def poll(self, token: str) -> int | None:
        sequence = self._poll_state[token]
        code = sequence[0]
        if len(sequence) > 1:
            sequence.pop(0)
        return code

    async def terminate(self, token: str) -> None:
        self.terminated.append(token)


@pytest.mark.unit
async def test_begin_builds_an_fdt_client_invocation_for_a_single_file() -> None:
    runner = _FakeRunner()
    port = FdtTransferPort(runner)
    await port.begin(_STAGE_IN)
    assert runner.started_argv[0] == (
        "java",
        "-jar",
        "/APSshare/bin/fdt.jar",
        "-c",
        "tomo1",
        "-d",
        "/data2/2BM/2026-06",
        "/local1/2BM/2026-06/scan_001.h5",
    )


@pytest.mark.unit
async def test_begin_adds_the_recursive_flag_for_a_directory_move() -> None:
    runner = _FakeRunner()
    port = FdtTransferPort(runner)
    await port.begin(
        TransferRequest(source="tomdet:/local1/exp", destination="tomo1:/data2/exp", recursive=True)
    )
    assert "-r" in runner.started_argv[0]


@pytest.mark.unit
async def test_observe_maps_running_then_zero_exit_to_active_then_succeeded() -> None:
    runner = _FakeRunner()
    runner.set_next_exit_sequence([None, 0])
    port = FdtTransferPort(runner)
    handle = await port.begin(_STAGE_IN)
    assert (await port.observe(handle)).state is TransferState.ACTIVE
    assert (await port.observe(handle)).state is TransferState.SUCCEEDED


@pytest.mark.unit
async def test_observe_maps_a_nonzero_exit_to_failed_with_the_code_in_detail() -> None:
    runner = _FakeRunner()
    runner.set_next_exit_sequence([3])
    port = FdtTransferPort(runner)
    handle = await port.begin(_STAGE_IN)
    progress = await port.observe(handle)
    assert progress.state is TransferState.FAILED
    assert "3" in (progress.detail or "")


@pytest.mark.unit
async def test_cancel_of_a_running_move_makes_it_observe_as_cancelled() -> None:
    runner = _FakeRunner()
    runner.set_next_exit_sequence([None])
    port = FdtTransferPort(runner)
    handle = await port.begin(_STAGE_IN)
    assert (await port.observe(handle)).state is TransferState.ACTIVE

    await port.cancel(handle)
    assert (await port.observe(handle)).state is TransferState.CANCELLED
    assert runner.terminated == [str(handle)]


@pytest.mark.unit
async def test_cancel_of_an_already_finished_move_is_a_noop() -> None:
    runner = _FakeRunner()
    runner.set_next_exit_sequence([0])
    port = FdtTransferPort(runner)
    handle = await port.begin(_STAGE_IN)
    assert (await port.observe(handle)).state is TransferState.SUCCEEDED

    await port.cancel(handle)
    assert (await port.observe(handle)).state is TransferState.SUCCEEDED
    assert runner.terminated == []


@pytest.mark.unit
async def test_malformed_location_is_rejected_before_launching_anything() -> None:
    runner = _FakeRunner()
    port = FdtTransferPort(runner)
    with pytest.raises(TransferRejectedError):
        await port.begin(TransferRequest(source="no-colon", destination=_DESTINATION))
    assert runner.started_argv == []


@pytest.mark.unit
async def test_a_failure_to_launch_maps_to_endpoint_unreachable() -> None:
    runner = _FakeRunner()
    runner.set_start_error(FileNotFoundError("java not found"))
    port = FdtTransferPort(runner)
    with pytest.raises(TransferEndpointUnreachableError):
        await port.begin(_STAGE_IN)


@pytest.mark.unit
async def test_adapter_satisfies_the_transfer_port_protocol() -> None:
    port = FdtTransferPort(_FakeRunner())
    assert isinstance(port, TransferPort)


@pytest.mark.unit
async def test_aclose_terminates_outstanding_moves() -> None:
    runner = _FakeRunner()
    runner.set_next_exit_sequence([None])
    port = FdtTransferPort(runner)
    handle = await port.begin(_STAGE_IN)
    await port.aclose()
    assert str(handle) in runner.terminated
