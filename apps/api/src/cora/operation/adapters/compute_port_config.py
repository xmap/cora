"""Operation BC factory: materialise a `ComputePort` from a config.

`build_compute_port(config)` returns either:

  - `InMemoryComputePort` (no config / `in_memory` substrate; the
    default + test convenience; the conduct surface is reachable but
    every job is Simulated)
  - `LocalProcessComputePort` (`local_process` substrate; runs jobs as
    OS subprocesses on the same host)

Single-substrate by design: ComputePort has one real adapter, so there
is NO routing registry (unlike `build_control_port`, which earned its
registry from multiple EPICS substrates). A second real substrate
(Slurm REST, Globus Compute) is the trigger that would introduce a
registry + a typed route table here, mirroring how ControlPort grew.

`ComputePortConfig` is a small typed shape rather than a full route
table for the same reason: one substrate plus its launch knobs, not a
per-prefix dispatch map.

## Lifecycle

The returned port owns the lifecycle of any substrate resource it
holds: `aclose()` terminates straggling subprocesses (local-process
path) or is a no-op (in-memory path). The caller does not track
individual jobs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.local_process_compute_port import LocalProcessComputePort

if TYPE_CHECKING:
    from cora.operation.ports.compute_port import ComputePort

ComputeSubstrate = Literal["in_memory", "local_process"]
"""Closed set of compute substrates with a shipped adapter.

`in_memory` is the Simulated fake; `local_process` runs subprocesses on
the host. Future substrates (`slurm`, `globus`) land as additive arms
here plus the registry this factory does not yet build.
"""


@dataclass(frozen=True)
class ComputePortConfig:
    """Deployment config for the single ComputePort substrate.

    `substrate` selects the adapter. `default_timeout_s` is the
    local-process wall-clock ceiling per job (ignored by the in-memory
    fake). A full route table is deferred to the second real substrate.
    """

    substrate: ComputeSubstrate = "in_memory"
    default_timeout_s: float = 3600.0


def build_compute_port(config: ComputePortConfig | None = None) -> ComputePort:
    """Materialise the ComputePort the conduct runtime talks to.

    None / `in_memory` returns an `InMemoryComputePort` (default + test
    convenience). `local_process` returns a `LocalProcessComputePort`
    with the configured wall-clock ceiling.
    """
    if config is None or config.substrate == "in_memory":
        return InMemoryComputePort()
    return LocalProcessComputePort(default_timeout_s=config.default_timeout_s)


__all__ = ["ComputePortConfig", "ComputeSubstrate", "build_compute_port"]
