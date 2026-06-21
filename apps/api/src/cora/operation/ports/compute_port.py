"""ComputePort: domain-shaped job submission for the Operation BC executor.

`ComputePort` is the async Protocol a Run-conducting runtime uses to
submit a compute job, await its terminal state, and fetch a reference
to the artifact it produced. Substrate details (a local subprocess,
a Slurm REST scheduler, Globus Compute) live behind concrete adapters;
the runtime never touches substrate-specific symbols directly.

This is the CONDUCT sibling of `ControlPort`. ControlPort generalises
value-IO across control-system substrates; ComputePort generalises
job submission across compute substrates. They sit in the same BC home
(`cora.operation.ports`) because both are seams the executor reaches
across to actuate the outside world: ControlPort drives hardware,
ComputePort drives a compute job. Per the seam model
([[project_seam_model]]) invoking an external compute substrate is the
same posture as invoking EPICS, not a competition with it.

## Earned, not minted

This port ships with exactly ONE real adapter (a local-process
executor) plus a test fake, following the adapter-first lesson behind
ControlPort ([[project_adapter_naming_research]],
[[feedback_port_generalization_trigger]]): a port surface is distilled
from a concrete adapter, never speculated ahead of one. The surface
below is what a local subprocess genuinely needs. When a second real
substrate arrives (Slurm REST, Globus Compute), generalise the surface
and introduce a routing registry then, exactly as ControlPort earned
its registry from a third substrate. No registry ships now.

## Domain vocabulary (substrate-neutral)

- **`JobSpec`** is the substrate-neutral description of the work:
  the command to run, its input and output URIs, validated parameters,
  and the resource shape it needs. Adapters translate it into a
  substrate launch (an argv + cwd for local-process; a batch script +
  `#SBATCH` directives for Slurm; a function payload for Globus).
- **`ComputeStatus`** is the closed terminal-state enum. A submitted
  job ends in exactly one of `Succeeded | Failed | Cancelled |
  TimedOut`. There is no in-flight value: `await_terminal_state`
  returns only when the job is done.
- **`ArtifactRef`** is a reference to the produced output, shaped to
  feed `RegisterDataset` 1:1 (uri + checksum + byte_size + media_type
  + conforms_to). The runtime captures it for provenance; a later
  `register_dataset` call records the resulting Dataset + Distribution.
- **`ComputeProvenance`** is the captured-once bundle the runtime
  snapshots onto the Run's terminal event for replay determinism
  ([[project_non_determinism_principle]]): job id, terminal status,
  the artifact ref, and the `ActuationKind` the adapter declares.

## Actuation kind

ComputePort reuses Operation's existing `ActuationKind`
(`Physical | Simulated | Hybrid`) rather than minting a parallel enum.
A real subprocess running a real solver is `Physical`; the in-memory
fake is `Simulated`. The adapter is the authority (mirroring how the
ControlPort registry's per-route `is_simulated` flag, not the adapter
class, decides): `provide_provenance_payload` lets the adapter stamp
the kind onto the provenance bundle, which rides the Run terminal
event so simulator-origin data can never be promoted to Production.

## Out of scope (deferred)

- **A routing registry / multi-substrate dispatch.** Triggers at the
  second real adapter, like ControlPort's registry.
- **Fire-and-reconcile submission** (submit returns immediately, a
  separate reconciler awaits the terminal state). The single blocking
  `submit` + `await_terminal_state` shape fits a local subprocess;
  the split is the Slurm-style second-adapter trigger.
- **Streaming / progress events** mid-job. A future `ComputeEventPort`
  sibling, by analogy to ControlPort's deferred `EventPort`.
- **Mid-job cancellation by handle.** Today the runtime cancels by
  cancelling the awaiting task; an explicit `cancel(job_id)` lands
  when a substrate needs server-side kill.

## Exceptions

Five exception families mirror CORA's standard shape and ControlPort's
posture: ComputePort is not REST-accessible; the conducting runtime
captures these as event-payload metadata, never surfacing them as HTTP
errors. A raised exception means the conduct failed; the runtime
records an aborted Run with the failure detail.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, NewType, Protocol, runtime_checkable

from cora.operation.ports.control_port import ActuationKind

JobId = NewType("JobId", str)
"""Opaque substrate job handle returned by `submit`.

A local-process adapter mints a process-scoped token; Slurm would use
its numeric job id; Globus Compute its task UUID. The runtime treats
it as an opaque correlation key it passes back to `await_terminal_state`
and `fetch_artifact_ref`, and snapshots onto the Run terminal event as
`producing_job_id` for audit.
"""


class ComputeStatus(StrEnum):
    """Closed terminal-state enum for a submitted compute job.

    A job that has reached `await_terminal_state` is in exactly one of
    these. There is no `Running` / `Pending` value: the port models
    submission-to-terminal, not in-flight polling, so the surface
    cannot represent a non-terminal job by construction.

    `Succeeded`: the job exited cleanly and produced its artifact.
    `Failed`: the job ran but exited non-zero / errored.
    `Cancelled`: the conduct was cancelled before the job finished.
    `TimedOut`: the job exceeded its allotted wall-clock budget.

    Only `Succeeded` warrants `fetch_artifact_ref`; the other three are
    failure terminals the runtime maps to an aborted Run.
    """

    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    TIMED_OUT = "TimedOut"

    @property
    def is_success(self) -> bool:
        """True only for `Succeeded`; the three failure terminals are False."""
        return self is ComputeStatus.SUCCEEDED


@dataclass(frozen=True)
class ComputeResources:
    """Resource shape a job needs, translated by the adapter to substrate knobs.

    Sourced from the bound ComputeNode Asset's settings (GPU/RAM) plus
    any per-run sizing. The local-process adapter largely ignores these
    (a subprocess takes what the box has); a Slurm adapter would map
    them to `--gres=gpu:N`, `--mem`, `--cpus-per-task`. Defaults express
    "unspecified, let the substrate decide."
    """

    gpu_count: int = 0
    gpu_memory_gb: float | None = None
    system_ram_gb: float | None = None
    cpus: int | None = None


@dataclass(frozen=True)
class JobSpec:
    """Substrate-neutral description of a compute job to submit.

    `command` is the argv the adapter launches (the local-process
    adapter runs it directly; a scheduler adapter wraps it in a batch
    script). `input_uris` and `output_uri` name the data the job reads
    and writes, opaque to the port. `parameters` is the validated
    parameter set (a Run's `effective_parameters`, already checked
    against the Method's `parameters_schema` upstream) carried for the
    adapter to render into argv / a config file. `resources` is the
    declared resource shape; `working_dir` and `env` are launch context.
    """

    command: tuple[str, ...]
    input_uris: tuple[str, ...] = ()
    output_uri: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict[str, Any])
    resources: ComputeResources = field(default_factory=ComputeResources)
    working_dir: str | None = None
    env: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class ArtifactRef:
    """Reference to the artifact a succeeded job produced.

    Shaped to feed `RegisterDataset` 1:1 so the runtime (or a later
    register-dataset call) can record the output Dataset + Distribution
    without reshaping: `uri` is where the bytes landed, `checksum_*`
    and `byte_size` verify them, `media_type` and `conforms_to` describe
    them. The adapter computes the checksum + size from the produced
    file on `fetch_artifact_ref`; `media_type` / `conforms_to` default
    to "unknown" when the substrate cannot infer them.

    The artifact may be a single file OR a directory of files (a default
    tomopy reconstruction writes a per-slice stack into a `{stem}_rec/`
    directory). For a single file, `checksum_algorithm` is `sha256` and
    `entry_count` is None. For a directory, `checksum_algorithm` is
    `sha256-tree` (a deterministic digest over the whole tree, see
    `_tree_hash.sha256_tree`), `byte_size` is the summed file sizes, and
    `entry_count` is the number of files. The 64-hex `checksum_value`
    format is identical for both, so it feeds `RegisterDataset` unchanged.
    """

    uri: str
    checksum_algorithm: str
    checksum_value: str
    byte_size: int
    media_type: str | None = None
    conforms_to: tuple[str, ...] = ()
    entry_count: int | None = None


@dataclass(frozen=True)
class ComputeProvenance:
    """Captured-once provenance bundle the runtime snapshots onto the Run.

    Assembled by the adapter's `provide_provenance_payload` so the
    adapter owns the `actuation_kind` determination (a real subprocess
    is `Physical`, the fake is `Simulated`). The runtime captures this
    at conduct time and threads `actuation_kind` + `job_id` +
    (`artifact_ref.uri`) onto the Run terminal event, so a replay folds
    the same provenance without re-running the job
    ([[project_non_determinism_principle]]).

    `is_simulated` is derived, not stored: any simulator touch
    disqualifies promotion, so `actuation_kind in {Simulated, Hybrid}`
    is the single source of truth, mirroring the ControlPort promotion
    gate's treatment of `Hybrid` as `Simulated`.
    """

    job_id: JobId
    status: ComputeStatus
    actuation_kind: ActuationKind
    artifact_ref: ArtifactRef | None = None

    @property
    def is_simulated(self) -> bool:
        """True when any part of the conduct touched a simulator.

        Derived from `actuation_kind`: `Simulated` and `Hybrid` both
        count (any simulator touch is disqualifying for promotion);
        only `Physical` is False.
        """
        return self.actuation_kind is not ActuationKind.PHYSICAL


class ComputeSubmitRejectedError(Exception):
    """The substrate refused to accept the job at submission time.

    Triggered when a scheduler rejects the spec (bad resource request,
    quota exceeded) or a local launch is malformed. Distinct from
    `ComputeNotAvailableError` (the substrate itself is reachable; it
    is the specific job it rejected).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Compute job submission rejected: {reason}")
        self.reason = reason


class ComputeNotAvailableError(Exception):
    """The compute substrate could not be reached at all.

    Triggered when the executable is missing (local-process), the
    scheduler endpoint is unreachable, or credentials are absent.
    A configuration / environment gap, not a per-job rejection.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Compute substrate not available: {reason}")
        self.reason = reason


class ComputeTimeoutError(Exception):
    """A hard await ceiling elapsed before the job reached a terminal state.

    Distinct from `ComputeStatus.TIMED_OUT`: that is the job's own
    wall-clock budget being exceeded (a recorded terminal outcome);
    this is the runtime giving up waiting on a substrate that never
    reported back at all. Carries the breached ceiling so logs
    distinguish "the job ran too long" from "we stopped waiting."
    """

    def __init__(self, job_id: JobId, timeout_s: float) -> None:
        super().__init__(f"Compute job {job_id!r} await exceeded {timeout_s}s")
        self.job_id = job_id
        self.timeout_s = timeout_s


class ComputeJobFailedError(Exception):
    """The job reached a `Failed` terminal and the runtime needs the detail.

    Carries a bounded failure message (an exit code, a stderr tail) so
    the runtime can record an honest abort reason on the Run. Adapters
    raise this rather than returning `Failed` silently when there is
    diagnostic detail worth preserving.
    """

    def __init__(self, job_id: JobId, reason: str) -> None:
        super().__init__(f"Compute job {job_id!r} failed: {reason}")
        self.job_id = job_id
        self.reason = reason


class ArtifactNotFoundError(Exception):
    """A succeeded job did not leave its declared artifact behind.

    Triggered when `fetch_artifact_ref` cannot stat the `output_uri`
    the spec promised. Almost always a job that reported success but
    wrote nowhere the adapter can see (wrong path, partial write); the
    runtime treats it as a conduct failure so no Dataset is registered
    against a phantom artifact.
    """

    def __init__(self, job_id: JobId, uri: str) -> None:
        super().__init__(f"Compute job {job_id!r} artifact not found at {uri!r}")
        self.job_id = job_id
        self.uri = uri


class NonRegularTreeEntryError(Exception):
    """A directory artifact contains a non-regular, non-symlink entry.

    Raised by the directory tree-hash helper when a socket, fifo, or
    device node sits under the artifact root: its bytes are not file
    content, so the tree cannot be digested in a stable way. The
    local-process adapter catches this and maps it to
    `ArtifactNotFoundError` so the conduct contract aborts cleanly; it is
    therefore never surfaced to the runtime directly. It lives here, next
    to the artifact errors, because the tree-hash helper is an adapter
    that depends on this port.
    """

    def __init__(self, path: str) -> None:
        super().__init__(f"non-regular entry in tree artifact: {path!r}")
        self.path = path


@runtime_checkable
class ComputePort(Protocol):
    """Domain-shaped job-submission port for compute substrates.

    Substrate-agnostic. Concrete adapters (`InMemoryComputePort`,
    `LocalProcessComputePort`, future `SlurmComputePort` /
    `GlobusComputePort`) implement the launch + poll + artifact-stat
    details. Per [[project_non_determinism_principle]] the conducting
    runtime captures the port's effects (job id, terminal status,
    artifact ref, actuation kind) into the Run's terminal event at
    conduct time, so a replay never re-submits.

    The submission model is single-blocking: `submit` then
    `await_terminal_state` complete one job within one conduct call.
    Fire-and-reconcile submission, a routing registry, mid-job
    streaming, and cancel-by-handle are deferred to their own triggers
    (see module docstring), keeping this surface to what a local
    subprocess genuinely needs.
    """

    async def submit(self, job_spec: JobSpec) -> JobId:
        """Submit `job_spec` to the substrate and return its job id.

        Returns as soon as the substrate accepts the job (a launched
        subprocess, an enqueued batch job). Raises
        `ComputeSubmitRejectedError` if the substrate refuses the spec
        or `ComputeNotAvailableError` if the substrate is unreachable.
        """
        ...

    async def await_terminal_state(self, job_id: JobId) -> ComputeStatus:
        """Block until `job_id` reaches a terminal state, then return it.

        Returns one of the four `ComputeStatus` terminals. May raise
        `ComputeTimeoutError` if a hard await ceiling elapses before the
        substrate reports a terminal state, or `ComputeJobFailedError`
        when there is diagnostic detail worth preserving alongside a
        `Failed` outcome.
        """
        ...

    async def fetch_artifact_ref(self, job_id: JobId) -> ArtifactRef:
        """Return an `ArtifactRef` for the output of a succeeded `job_id`.

        Only valid after `await_terminal_state` returned `Succeeded`.
        Raises `ArtifactNotFoundError` if the job's declared output is
        not where the adapter expects it.
        """
        ...

    def provide_provenance_payload(
        self,
        job_id: JobId,
        status: ComputeStatus,
        artifact_ref: ArtifactRef | None,
    ) -> ComputeProvenance:
        """Assemble the `ComputeProvenance` bundle for this job.

        Pure assembly (no IO): the adapter stamps the `ActuationKind`
        it is the authority for (`Physical` for a real substrate,
        `Simulated` for the fake) onto the captured job id, terminal
        status, and artifact ref. The runtime threads this onto the Run
        terminal event for replay-deterministic provenance.
        """
        ...

    async def aclose(self) -> None:
        """Release any substrate resources; idempotent.

        Provided so composition code can call `aclose()` on any
        `ComputePort` without branching on type (mirrors
        `ControlPort.aclose`). The in-memory fake is a no-op; a
        local-process adapter terminates any straggling subprocesses.
        """
        ...


__all__ = [
    "ArtifactNotFoundError",
    "ArtifactRef",
    "ComputeJobFailedError",
    "ComputeNotAvailableError",
    "ComputePort",
    "ComputeProvenance",
    "ComputeResources",
    "ComputeStatus",
    "ComputeSubmitRejectedError",
    "ComputeTimeoutError",
    "JobId",
    "JobSpec",
    "NonRegularTreeEntryError",
]
