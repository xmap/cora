"""Operation BC factory: materialise a `DecidePort` from a config.

`build_decide_port(config)` returns a `DecidePort` for the configured
decider substrate:

  - `InMemoryDecidePort` (no config / `in_memory` substrate; the default +
    test convenience; replays seeded advice then advises Stop)
  - `GridWalkDecidePort` (`grid_walk` substrate; a deterministic, stateless
    grid/sweep decider over the SteeringSpace, no external optimizer)

Two in-CORA arms today, mirroring `build_compute_port`: a later external
optimizer adapter (gpcam) lands as an additive arm here, and a routing
registry is earned only when that arrives, exactly as ControlPort earned its
registry from a third substrate and ComputePort deferred its.

## Lifecycle

The returned port owns the lifecycle of any decider resource it holds:
`aclose()` is a no-op for the in-CORA deciders and would release a model
client / optimizer subprocess for a real external adapter. The caller
`aclose()`s it at teardown without branching on type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cora.operation.adapters.grid_walk_decide_port import GridWalkDecidePort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort

if TYPE_CHECKING:
    from cora.operation.ports.decide_port import DecidePort

DecideSubstrate = Literal["in_memory", "grid_walk"]
"""Closed set of decider substrates with a shipped adapter.

`in_memory` is the deterministic fake; `grid_walk` is the in-CORA grid/sweep
decider. A future external optimizer (such as `gpcam`) lands as an additive
arm here plus the registry this factory does not yet build.
"""


@dataclass(frozen=True)
class DecidePortConfig:
    """Deployment config for the DecidePort substrate.

    `substrate` selects the adapter. `points_per_axis` is the grid-walk
    resolution for continuous axes (ignored by the in-memory fake and by
    axes that carry explicit choices). A full route table is deferred to the
    external optimizer, mirroring `ComputePortConfig`.
    """

    substrate: DecideSubstrate = "in_memory"
    points_per_axis: int = 5


def build_decide_port(config: DecidePortConfig | None = None) -> DecidePort:
    """Materialise the DecidePort the conduct loop talks to.

    None or the `in_memory` substrate returns an `InMemoryDecidePort` (the
    default + test convenience). `grid_walk` returns a `GridWalkDecidePort`
    at the configured resolution. A future external optimizer adds its arm
    here as it is earned, exactly as `build_compute_port` grew its
    `local_process` arm.
    """
    resolved = config if config is not None else DecidePortConfig()
    if resolved.substrate == "in_memory":
        return InMemoryDecidePort()
    if resolved.substrate == "grid_walk":
        return GridWalkDecidePort(points_per_axis=resolved.points_per_axis)
    raise ValueError(  # pragma: no cover
        f"unsupported decide substrate: {resolved.substrate!r}"
    )


__all__ = ["DecidePortConfig", "DecideSubstrate", "build_decide_port"]
