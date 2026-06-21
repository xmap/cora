"""Integration tests for `LocalProcessComputePort` against real subprocesses.

Hermetic: each test launches a short Python one-liner via the same
interpreter (no real TomoPy, no network, no DB), so it exercises the
real subprocess + filesystem path without external dependencies. Covers
the success / failure / timeout / missing-binary / missing-artifact
branches and the Physical actuation kind.
"""

import hashlib
import sys
from pathlib import Path

import pytest

from cora.operation.adapters._tree_hash import sha256_tree
from cora.operation.adapters.local_process_compute_port import LocalProcessComputePort
from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputeStatus,
    JobSpec,
)
from cora.operation.ports.control_port import ActuationKind

_PAYLOAD = b"reconstructed-volume-bytes"


def _write_file_spec(out: Path) -> JobSpec:
    """A job that writes `_PAYLOAD` to `out` and exits 0."""
    return JobSpec(
        command=(
            sys.executable,
            "-c",
            f"import pathlib; pathlib.Path({str(out)!r}).write_bytes({_PAYLOAD!r})",
        ),
        output_uri=out.as_uri(),
    )


@pytest.mark.integration
async def test_successful_subprocess_succeeds_with_real_artifact_checksum(tmp_path: Path) -> None:
    out = tmp_path / "recon.h5"
    port = LocalProcessComputePort()
    job_id = await port.submit(_write_file_spec(out))

    assert await port.await_terminal_state(job_id) is ComputeStatus.SUCCEEDED

    artifact = await port.fetch_artifact_ref(job_id)
    assert artifact.uri == out.as_uri()
    assert artifact.byte_size == len(_PAYLOAD)
    assert artifact.checksum_algorithm == "sha256"
    assert artifact.checksum_value == hashlib.sha256(_PAYLOAD).hexdigest()


@pytest.mark.integration
async def test_provenance_declares_physical_actuation(tmp_path: Path) -> None:
    out = tmp_path / "recon.h5"
    port = LocalProcessComputePort()
    job_id = await port.submit(_write_file_spec(out))
    status = await port.await_terminal_state(job_id)
    artifact = await port.fetch_artifact_ref(job_id)

    provenance = port.provide_provenance_payload(job_id, status, artifact)
    assert provenance.actuation_kind is ActuationKind.PHYSICAL
    assert provenance.is_simulated is False


@pytest.mark.integration
async def test_nonzero_exit_raises_job_failed_with_stderr_tail() -> None:
    port = LocalProcessComputePort()
    job_id = await port.submit(
        JobSpec(
            command=(sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"),
        )
    )
    with pytest.raises(ComputeJobFailedError) as exc_info:
        await port.await_terminal_state(job_id)
    assert "exit code 3" in str(exc_info.value)
    assert "boom" in str(exc_info.value)


@pytest.mark.integration
async def test_missing_executable_raises_not_available() -> None:
    port = LocalProcessComputePort()
    with pytest.raises(ComputeNotAvailableError):
        await port.submit(JobSpec(command=("cora-no-such-binary-xyz",)))


@pytest.mark.integration
async def test_succeeded_but_missing_output_raises_artifact_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "never_written.h5"
    port = LocalProcessComputePort()
    job_id = await port.submit(
        JobSpec(command=(sys.executable, "-c", "pass"), output_uri=missing.as_uri())
    )
    assert await port.await_terminal_state(job_id) is ComputeStatus.SUCCEEDED
    with pytest.raises(ArtifactNotFoundError):
        await port.fetch_artifact_ref(job_id)


def _write_tiff_stack_spec(out_dir: Path, slices: int) -> JobSpec:
    """A job that writes a `{out_dir}/slice_NNNN.tif` stack and exits 0."""
    return JobSpec(
        command=(
            sys.executable,
            "-c",
            (
                "import pathlib; "
                f"d = pathlib.Path({str(out_dir)!r}); d.mkdir(parents=True, exist_ok=True); "
                f"[(d / f'slice_{{i:04d}}.tif').write_bytes(b'slice-%d' % i) "
                f"for i in range({slices})]"
            ),
        ),
        output_uri=out_dir.as_uri(),
    )


@pytest.mark.integration
async def test_directory_output_succeeds_with_tree_hash_artifact(tmp_path: Path) -> None:
    out_dir = tmp_path / "sample_rec"
    port = LocalProcessComputePort()
    job_id = await port.submit(_write_tiff_stack_spec(out_dir, slices=5))

    assert await port.await_terminal_state(job_id) is ComputeStatus.SUCCEEDED

    artifact = await port.fetch_artifact_ref(job_id)
    expected_digest, expected_size, expected_count = sha256_tree(out_dir)
    assert artifact.checksum_algorithm == "sha256-tree"
    assert artifact.checksum_value == expected_digest
    assert artifact.byte_size == expected_size
    assert artifact.entry_count == expected_count == 5
    assert artifact.uri == out_dir.as_uri()


@pytest.mark.integration
async def test_empty_directory_output_raises_artifact_not_found(tmp_path: Path) -> None:
    out_dir = tmp_path / "empty_rec"
    port = LocalProcessComputePort()
    job_id = await port.submit(
        JobSpec(
            command=(
                sys.executable,
                "-c",
                f"import pathlib; pathlib.Path({str(out_dir)!r}).mkdir(parents=True)",
            ),
            output_uri=out_dir.as_uri(),
        )
    )
    assert await port.await_terminal_state(job_id) is ComputeStatus.SUCCEEDED
    with pytest.raises(ArtifactNotFoundError):
        await port.fetch_artifact_ref(job_id)


@pytest.mark.integration
async def test_overrunning_job_times_out_and_is_killed() -> None:
    port = LocalProcessComputePort(default_timeout_s=0.2)
    job_id = await port.submit(
        JobSpec(command=(sys.executable, "-c", "import time; time.sleep(30)"))
    )
    assert await port.await_terminal_state(job_id) is ComputeStatus.TIMED_OUT
    await port.aclose()


@pytest.mark.integration
async def test_empty_command_is_rejected() -> None:
    port = LocalProcessComputePort()
    from cora.operation.ports.compute_port import ComputeSubmitRejectedError

    with pytest.raises(ComputeSubmitRejectedError):
        await port.submit(JobSpec(command=()))
