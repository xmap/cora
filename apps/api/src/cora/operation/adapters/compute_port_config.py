"""Operation BC factory: materialise a `ComputePort` from a config.

`build_compute_port(config)` returns either:

  - `InMemoryComputePort` (no config / `in_memory` substrate; the
    default + test convenience; the conduct surface is reachable but
    every job is Simulated)
  - `LocalProcessComputePort` (`local_process` substrate; runs jobs as
    OS subprocesses on the same host)
  - `GlobusComputePort` (`globus` substrate; runs jobs on a remote Globus
    Compute endpoint such as an ALCF Polaris node)

The `globus` substrate is the SECOND real adapter, the off-host trigger
this factory was written to anticipate. It is NOT constructed from the
flat config here: it needs an authorized client + endpoint id + a remote
artifact probe a config string cannot carry, so the composition root
builds the `GlobusComputePort` and passes the ready instance via the
`prebuilt_port` argument. This factory owns the SELECTION seam (dispatch on
`substrate`), which IS the registry the second substrate earns, in the
lightest form that fits: a closed substrate literal, not yet a
per-prefix route table.

A THIRD substrate (Slurm REST) that also needs injected wiring is the
trigger to promote this to a real route registry AND to extract a shared
poll-to-terminal helper from `GlobusComputePort` (the await loop both
remote substrates share). Slurm lands as an additive `slurm` arm then.
`ComputePortConfig` stays a small typed shape (substrate selector +
launch knobs), not a full route table, until that third substrate.

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

ComputeSubstrate = Literal["in_memory", "local_process", "globus"]
"""Closed set of compute substrates with a shipped adapter.

`in_memory` is the Simulated fake; `local_process` runs subprocesses on
the host; `globus` runs jobs on a remote Globus Compute endpoint (the
`prebuilt_port`-injected `GlobusComputePort`). A future `slurm` substrate
lands as an additive arm here plus the route registry this factory does
not yet build.
"""


@dataclass(frozen=True)
class ComputePortConfig:
    """Deployment config for the selected ComputePort substrate.

    `substrate` selects the adapter. `default_timeout_s` is the wall-clock
    ceiling per job (ignored by the in-memory fake). A full route table is
    deferred to the third real substrate. The `globus` substrate is built
    at the composition root and injected via `build_compute_port(prebuilt_port=...)`
    because its client + endpoint + artifact probe cannot ride a flat config.
    """

    substrate: ComputeSubstrate = "in_memory"
    default_timeout_s: float = 3600.0


def build_compute_port(
    config: ComputePortConfig | None = None,
    *,
    prebuilt_port: ComputePort | None = None,
) -> ComputePort:
    """Materialise the ComputePort the conduct runtime talks to.

    None / `in_memory` returns an `InMemoryComputePort` (default + test
    convenience). `local_process` returns a `LocalProcessComputePort` with
    the configured wall-clock ceiling. `globus` returns the `prebuilt_port`
    `GlobusComputePort` the composition root constructed (its client +
    endpoint + artifact probe cannot be built from the flat config); a
    `globus` substrate with no `prebuilt_port` is a wiring error.
    """
    if config is None or config.substrate == "in_memory":
        return InMemoryComputePort()
    if config.substrate == "globus":
        if prebuilt_port is None:
            msg = (
                "compute substrate 'globus' requires a prebuilt_port GlobusComputePort "
                "(no flat-config build path)"
            )
            raise ValueError(msg)
        return prebuilt_port
    return LocalProcessComputePort(default_timeout_s=config.default_timeout_s)


__all__ = ["ComputePortConfig", "ComputeSubstrate", "build_compute_port"]
