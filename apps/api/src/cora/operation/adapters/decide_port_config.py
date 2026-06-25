"""Operation BC factory: materialise a `DecidePort` from a config.

`build_decide_port(config)` returns a `DecidePort` for the configured
decider substrate. Today there is exactly one shipped adapter, the
`InMemoryDecidePort` fake, so `None` / `in_memory` is the only arm:

  - `InMemoryDecidePort` (no config / `in_memory` substrate; the default +
    test convenience; replays seeded advice then advises Stop)

Single-substrate by design, mirroring `build_compute_port`: a real in-CORA
decider (`GridWalkDecidePort`, next slice) and later an external optimizer
adapter (gpCAM) land as additive arms here, and a routing registry is
earned only when a second real decider arrives, exactly as ControlPort
earned its registry from a third substrate and ComputePort deferred its.

## Lifecycle

The returned port owns the lifecycle of any decider resource it holds:
`aclose()` is a no-op for the in-memory fake and releases a model client /
optimizer subprocess for a real adapter. The caller `aclose()`s it at
teardown without branching on type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort

if TYPE_CHECKING:
    from cora.operation.ports.decide_port import DecidePort

DecideSubstrate = Literal["in_memory"]
"""Closed set of decider substrates with a shipped adapter.

`in_memory` is the deterministic fake. Future substrates (`grid_walk`, then
an external optimizer such as `gpcam`) land as additive arms here plus the
registry this factory does not yet build.
"""


@dataclass(frozen=True)
class DecidePortConfig:
    """Deployment config for the single DecidePort substrate.

    `substrate` selects the adapter. A full route table is deferred to the
    second real decider, mirroring `ComputePortConfig`.
    """

    substrate: DecideSubstrate = "in_memory"


def build_decide_port(config: DecidePortConfig | None = None) -> DecidePort:
    """Materialise the DecidePort the conduct loop talks to.

    None or the `in_memory` substrate returns an `InMemoryDecidePort` (the
    default + test convenience, and the only shipped arm today). A real
    decider (a grid walker, then an external optimizer) adds its arm here as
    it is earned, exactly as `build_compute_port` grew its `local_process`
    arm. The trailing raise is defensive-in-depth: if `DecideSubstrate` gains
    a value, this surfaces the missing arm rather than silently returning the
    fake.
    """
    if config is None or config.substrate == "in_memory":
        return InMemoryDecidePort()
    raise ValueError(  # pragma: no cover
        f"unsupported decide substrate: {config.substrate!r}"
    )


__all__ = ["DecidePortConfig", "DecideSubstrate", "build_decide_port"]
