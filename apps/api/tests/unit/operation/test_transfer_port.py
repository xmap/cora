"""Behavioural triage scenario for `TransferPort` + `InMemoryTransferPort`.

Grounds the design triage (is a transfer a conductor step, or a long-running
edge job?) in the real shape of a 2-BM data sync. DMagic, the tool 2-BM uses
today, syncs an experiment's raw directory and its reconstructed (`_rec`)
sibling to a managed store; it starts the move and lets it run, it does not
block on it. These tests drive the same begin-observe-until-terminal loop an
edge job would run, and exercise the cases that decide the triage: a move that
is polled across several `Active` observations, a re-sync that skips unchanged
files, a partial move, a credential-expiry suspension mid-sync, and cancel.

The contrast with the compute path is the finding: a compute job is awaited in
one blocking call, but a transfer is begun once and observed to a terminal on
the engine's own cadence, through a non-terminal `Suspended`, which is why it
wants a long-running edge job rather than a synchronous step.
"""

import pytest

from cora.operation.adapters.in_memory_transfer_port import InMemoryTransferPort
from cora.operation.ports.transfer_port import (
    TransferHandle,
    TransferPort,
    TransferProgress,
    TransferRejectedError,
    TransferRequest,
    TransferState,
)

_SOURCE = "aps-dm:/gdata/dm/2BM/exp123/"
_DESTINATION = "globus-archive:/archive/2BM/exp123/"
_RAW_SYNC = TransferRequest(source=_SOURCE, destination=_DESTINATION, recursive=True)
_RESYNC = TransferRequest(
    source=_SOURCE, destination=_DESTINATION, recursive=True, skip_unchanged=True
)

_MAX_POLLS = 20


async def _drive_to_terminal(
    port: TransferPort, handle: TransferHandle
) -> tuple[TransferProgress, list[TransferState]]:
    """Poll `observe` like an edge job would: until a terminal, waiting through Suspended.

    Returns the terminal snapshot plus the ordered states seen, so a test can
    assert the move passed through (for example) a `Suspended` observation
    before terminating. Bounded so a misseeded test fails loudly instead of
    looping forever.
    """
    seen: list[TransferState] = []
    for _ in range(_MAX_POLLS):
        progress = await port.observe(handle)
        seen.append(progress.state)
        if progress.state.is_terminal:
            return progress, seen
    msg = f"transfer {handle!r} never reached a terminal within {_MAX_POLLS} polls"
    raise AssertionError(msg)


@pytest.mark.unit
async def test_directory_sync_polled_across_active_observations_succeeds() -> None:
    port = InMemoryTransferPort()
    port.set_next_progression(
        (
            TransferProgress(state=TransferState.PENDING),
            TransferProgress(state=TransferState.ACTIVE, files_total=400, files_moved=120),
            TransferProgress(state=TransferState.ACTIVE, files_total=400, files_moved=380),
            TransferProgress(
                state=TransferState.SUCCEEDED, files_total=400, files_moved=400, bytes_moved=8_000
            ),
        )
    )
    handle = await port.begin(_RAW_SYNC)
    terminal, seen = await _drive_to_terminal(port, handle)

    assert terminal.state is TransferState.SUCCEEDED
    assert terminal.files_moved == 400
    assert TransferState.ACTIVE in seen
    assert seen[-1] is TransferState.SUCCEEDED


@pytest.mark.unit
async def test_resync_of_rec_directory_skips_unchanged_and_still_succeeds() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(
        TransferState.SUCCEEDED, files_total=400, files_moved=12, files_skipped=388
    )
    handle = await port.begin(_RESYNC)
    progress = await port.observe(handle)

    assert progress.state is TransferState.SUCCEEDED
    assert progress.files_skipped == 388
    assert progress.is_partial is False


@pytest.mark.unit
async def test_partial_move_is_failed_terminal_carrying_a_failed_count() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(
        TransferState.FAILED,
        files_total=400,
        files_moved=397,
        files_failed=3,
        detail="3 subtasks failed",
    )
    handle = await port.begin(_RAW_SYNC)
    progress = await port.observe(handle)

    assert progress.state is TransferState.FAILED
    assert progress.is_partial is True
    assert progress.files_failed == 3
    assert progress.files_moved == 397


@pytest.mark.unit
async def test_total_failure_is_failed_terminal_that_is_not_partial() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(TransferState.FAILED, files_total=400, files_moved=0, files_failed=400)
    handle = await port.begin(_RAW_SYNC)
    progress = await port.observe(handle)

    assert progress.state is TransferState.FAILED
    assert progress.is_partial is False


@pytest.mark.unit
async def test_credential_expiry_suspends_mid_sync_then_resumes_to_succeeded() -> None:
    port = InMemoryTransferPort()
    port.set_next_progression(
        (
            TransferProgress(state=TransferState.ACTIVE, files_total=400, files_moved=200),
            TransferProgress(
                state=TransferState.SUSPENDED, files_moved=200, detail="credential expired"
            ),
            TransferProgress(state=TransferState.ACTIVE, files_total=400, files_moved=350),
            TransferProgress(state=TransferState.SUCCEEDED, files_total=400, files_moved=400),
        )
    )
    handle = await port.begin(_RAW_SYNC)
    terminal, seen = await _drive_to_terminal(port, handle)

    assert TransferState.SUSPENDED in seen
    assert TransferState.SUSPENDED.is_terminal is False
    assert terminal.state is TransferState.SUCCEEDED


@pytest.mark.unit
async def test_substrate_refusal_raises_transfer_rejected_at_begin() -> None:
    port = InMemoryTransferPort()
    port.set_next_begin_error(TransferRejectedError("destination quota exceeded"))
    with pytest.raises(TransferRejectedError):
        await port.begin(_RAW_SYNC)


@pytest.mark.unit
async def test_cancel_makes_subsequent_observation_report_cancelled() -> None:
    port = InMemoryTransferPort()
    port.set_next_progression(
        (
            TransferProgress(state=TransferState.ACTIVE, files_total=400, files_moved=120),
            TransferProgress(state=TransferState.ACTIVE, files_total=400, files_moved=260),
        )
    )
    handle = await port.begin(_RAW_SYNC)
    in_flight = await port.observe(handle)
    assert in_flight.state is TransferState.ACTIVE

    await port.cancel(handle)
    after = await port.observe(handle)
    assert after.state is TransferState.CANCELLED
    assert after.files_moved == 120


@pytest.mark.unit
async def test_cancel_of_already_terminal_move_is_a_noop() -> None:
    port = InMemoryTransferPort()
    port.set_next_terminal(TransferState.SUCCEEDED, files_total=400, files_moved=400)
    handle = await port.begin(_RAW_SYNC)
    assert (await port.observe(handle)).state is TransferState.SUCCEEDED

    await port.cancel(handle)
    assert (await port.observe(handle)).state is TransferState.SUCCEEDED


@pytest.mark.unit
async def test_in_memory_double_satisfies_the_transfer_port_protocol() -> None:
    port = InMemoryTransferPort()
    assert isinstance(port, TransferPort)


@pytest.mark.unit
async def test_aclose_is_idempotent_noop() -> None:
    port = InMemoryTransferPort()
    await port.aclose()
    await port.aclose()
