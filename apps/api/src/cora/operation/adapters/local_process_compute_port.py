"""Local-process `ComputePort` adapter: run a compute job as a subprocess.

The first real `ComputePort` substrate. It launches the job spec's
command as an OS subprocess on the same host, polls it to a terminal
state, and stats the produced output file into an `ArtifactRef`. This
is the smallest real executor that earns the port: a beamline
workstation running a reconstruction (`tomopy recon ...`) directly,
with no scheduler. A Slurm / Globus adapter is the second-substrate
trigger that would introduce a routing registry, exactly as ControlPort
earned its registry from a third substrate.

## Mapping to the substrate

- `submit` spawns `job_spec.command` via `asyncio.create_subprocess_exec`
  in `job_spec.working_dir` with `job_spec.env`, captures stdout/stderr,
  and returns a process-scoped `JobId`. A missing executable raises
  `ComputeNotAvailableError` (an environment gap); any other spawn
  failure raises `ComputeSubmitRejectedError`.
- `await_terminal_state` awaits the process under a wall-clock ceiling
  (`default_timeout_s`). Exit 0 -> `Succeeded`. A non-zero exit raises
  `ComputeJobFailedError` carrying a bounded stderr tail (richer than a
  bare `Failed`). Exceeding the ceiling kills the process and returns
  `TimedOut`.
- `fetch_artifact_ref` resolves `job_spec.output_uri` to a filesystem
  path, stats it, and computes a sha256 + byte size. A missing output
  on a succeeded job raises `ArtifactNotFoundError`.
- `provide_provenance_payload` stamps `ActuationKind.PHYSICAL`: a real
  subprocess running a real solver is physical actuation, so any Dataset
  it produces is promotable (unlike the simulated in-memory fake).

The adapter does NOT interpret `job_spec.parameters` or
`job_spec.resources`; the caller renders parameters into `command`
argv, and a single-host subprocess takes whatever the box has. A
scheduler adapter is where `resources` becomes `--gres` / `--mem`.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputeProvenance,
    ComputeStatus,
    ComputeSubmitRejectedError,
    JobId,
)
from cora.operation.ports.control_port import ActuationKind

if TYPE_CHECKING:
    from cora.operation.ports.compute_port import JobSpec

# A failed job's stderr tail is preserved on the abort reason, which is
# bounded by RunAbortReason (1-500). Keep the adapter's slice well under
# that so the runtime's prefix + truncation marker always fit.
_STDERR_TAIL_MAX = 300


class LocalProcessComputePort:
    """`ComputePort` over `asyncio` subprocesses on the local host."""

    def __init__(self, *, default_timeout_s: float = 3600.0) -> None:
        self._default_timeout_s = default_timeout_s
        self._jobs: dict[JobId, tuple[asyncio.subprocess.Process, JobSpec]] = {}
        self._counter = 0

    async def submit(self, job_spec: JobSpec) -> JobId:
        if not job_spec.command:
            raise ComputeSubmitRejectedError("job spec has an empty command")
        try:
            process = await asyncio.create_subprocess_exec(
                *job_spec.command,
                cwd=job_spec.working_dir,
                env={**os.environ, **job_spec.env} if job_spec.env else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ComputeNotAvailableError(
                f"executable not found: {job_spec.command[0]!r}"
            ) from exc
        except OSError as exc:
            raise ComputeSubmitRejectedError(f"could not launch job: {exc}") from exc
        self._counter += 1
        job_id = JobId(f"local-{process.pid}-{self._counter}")
        self._jobs[job_id] = (process, job_spec)
        return job_id

    async def await_terminal_state(self, job_id: JobId) -> ComputeStatus:
        process, _ = self._jobs[job_id]
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._default_timeout_s
            )
        except TimeoutError:
            process.kill()
            with contextlib.suppress(ProcessLookupError):
                await process.wait()
            return ComputeStatus.TIMED_OUT
        if process.returncode == 0:
            return ComputeStatus.SUCCEEDED
        raise ComputeJobFailedError(
            job_id,
            f"exit code {process.returncode}: {_stderr_tail(stderr)}",
        )

    async def fetch_artifact_ref(self, job_id: JobId) -> ArtifactRef:
        _, job_spec = self._jobs[job_id]
        if job_spec.output_uri is None:
            raise ArtifactNotFoundError(job_id, "<no output_uri on job spec>")
        path = _path_from_uri(job_spec.output_uri)
        if path is None or not path.is_file():
            raise ArtifactNotFoundError(job_id, job_spec.output_uri)
        digest = await asyncio.to_thread(_sha256_of, path)
        return ArtifactRef(
            uri=job_spec.output_uri,
            checksum_algorithm="sha256",
            checksum_value=digest,
            byte_size=path.stat().st_size,
        )

    def provide_provenance_payload(
        self,
        job_id: JobId,
        status: ComputeStatus,
        artifact_ref: ArtifactRef | None,
    ) -> ComputeProvenance:
        return ComputeProvenance(
            job_id=job_id,
            status=status,
            actuation_kind=ActuationKind.PHYSICAL,
            artifact_ref=artifact_ref,
        )

    async def aclose(self) -> None:
        """Terminate any straggling subprocesses; idempotent.

        A well-behaved conduct awaits each job to terminal, so the
        process map is usually empty by shutdown. This is the backstop
        for a job still running when the app tears down.
        """
        for process, _ in self._jobs.values():
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                with contextlib.suppress(Exception):
                    await process.wait()
        self._jobs.clear()


def _stderr_tail(stderr: bytes | None) -> str:
    """Decode and bound a process's stderr for an abort reason."""
    if not stderr:
        return "<no stderr>"
    text = stderr.decode(errors="replace").strip()
    if len(text) <= _STDERR_TAIL_MAX:
        return text
    return "..." + text[-_STDERR_TAIL_MAX:]


def _path_from_uri(uri: str) -> Path | None:
    """Resolve a `file://` URI or a bare path to a Path; None if not local.

    Accepts `file:///abs/path` and bare `/abs/path` / `rel/path`. Any
    non-file scheme (http, s3, globus) returns None: this adapter only
    produces local artifacts.
    """
    parsed = urlparse(uri)
    if parsed.scheme in ("", "file"):
        return Path(unquote(parsed.path) if parsed.scheme == "file" else uri)
    return None


def _sha256_of(path: Path) -> str:
    """Stream a file through sha256 (chunked; tolerates large artifacts)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["LocalProcessComputePort"]
