"""Operation BC factory: materialise a `DecidePort` from a config.

`build_decide_port(config)` returns a `DecidePort` for the configured
decider substrate:

  - `InMemoryDecidePort` (no config / `in_memory` substrate; the default +
    test convenience; replays seeded advice then advises Stop)
  - `GridWalkDecidePort` (`grid_walk` substrate; a deterministic, stateless
    grid/sweep decider over the SteeringSpace, no external optimizer)
  - `SobolDecidePort` (`sobol` substrate; a deterministic, stateless Sobol
    initial-design seeder; needs the optional `bo` dependency group)
  - `BoTorchDecidePort` (`botorch` substrate; a Gaussian-process Bayesian-
    optimization brain; forward-runs-only, needs the optional `bo` group)
  - `StagedDecidePort` (`staged` substrate; a two-phase composite that seeds
    with `sobol` then hands off to `botorch` on a successful-observation
    count; needs the optional `bo` group)
  - `LlmDecidePort` (`llm` substrate; an LLM steering brain; needs an injected
    `LLM` port via the `llm` argument, not an optional dependency group)

These arms mirror `build_compute_port`, and a routing registry is earned only
when the substrate count makes the if-chain unwieldy, exactly as ControlPort
earned its registry from a third substrate and ComputePort deferred its.

## Wire-selectable vs internally-selectable substrates

`DecideSubstrate` is the FULL set of substrates the factory can build.
`WireDecideSubstrate` is the SUBSET a remote caller may select over the
HTTP/MCP wire. They are deliberately decoupled: a new substrate becomes
factory-buildable (and usable by in-process composition such as the staged
decider or a deployment config) the moment it is added to `DecideSubstrate`,
WITHOUT silently becoming selectable over the wire, where its config fields
may have no wire representation yet. A substrate is promoted to the wire only
when its wire config is deliberately designed. The wire request model
(`DecideConfigRequest` in `_advise_wire`) types its `substrate` field with
`WireDecideSubstrate`, so the two sets cannot drift by accident.

## Lifecycle

The returned port owns the lifecycle of any decider resource it holds:
`aclose()` is a no-op for the in-CORA deciders and would release a model
client / optimizer subprocess for a real external adapter. The caller
`aclose()`s it at teardown without branching on type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cora.operation.adapters.botorch_decide_port import BoTorchDecidePort
from cora.operation.adapters.grid_walk_decide_port import GridWalkDecidePort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.adapters.llm_decide_port import LlmDecidePort
from cora.operation.adapters.sobol_decide_port import SobolDecidePort
from cora.operation.adapters.staged_decide_port import StagedDecidePort

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from cora.infrastructure.ports.clock import Clock
    from cora.infrastructure.ports.llm import LLM
    from cora.infrastructure.ports.spend_guard import SpendGuard
    from cora.operation.ports.decide_port import DecidePort, SteeringLlmCall

DecideSubstrate = Literal["in_memory", "grid_walk", "sobol", "botorch", "staged", "llm"]
"""The full set of decider substrates `build_decide_port` can materialise.

`in_memory` is the deterministic fake; `grid_walk` is the in-CORA grid/sweep
decider; `sobol` is the Sobol initial-design seeder; `botorch` is the GP
Bayesian-optimization brain; `staged` is the two-phase sobol-then-botorch
composite (those three need the optional `bo` group); `llm` is the LLM
steering brain (needs an injected `LLM` port via `build_decide_port`'s `llm`
argument, not an optional dependency group). Adding an arm here makes it
factory-buildable for in-process composition + deployment config; promoting
it to the wire is a separate, deliberate step (see `WireDecideSubstrate`).
"""

WireDecideSubstrate = Literal["in_memory", "grid_walk"]
"""The subset of substrates a remote caller may select over the HTTP/MCP wire.

Narrower than `DecideSubstrate` on purpose: a substrate is wire-selectable
only once its config has a designed wire representation. `sobol`, the GP
brain, and `llm` are factory-buildable but NOT wire-selectable yet, so
widening `DecideSubstrate` never silently exposes an unconfigurable substrate
on the live route. The wire request model types its `substrate` with this
Literal.
"""


@dataclass(frozen=True)
class DecidePortConfig:
    """Deployment config for the DecidePort substrate.

    `substrate` selects the adapter. `points_per_axis` is the grid-walk
    resolution for continuous axes. `min_observations` / `num_restarts` /
    `raw_samples` / `seed` tune the BoTorch brain (the `botorch` substrate,
    and the brain child of the `staged` substrate). `staged_threshold` is the
    successful-observation count at which the `staged` composite hands off
    from the Sobol seeder to the brain; it must be >= `min_observations`. A
    full route table is deferred, mirroring `ComputePortConfig`.
    """

    substrate: DecideSubstrate = "in_memory"
    spend_agent_id: UUID | None = None
    """The agent whose budget gates the llm substrate's calls, or None for
    an ungated brain. Set in-process by agent drivers (steer_experiment);
    deliberately NOT exposed on the conduct wire models, so route callers
    cannot attribute their spend to an agent."""
    points_per_axis: int = 5
    min_observations: int = 5
    num_restarts: int = 10
    raw_samples: int = 256
    seed: int = 0
    staged_threshold: int = 5


def build_decide_port(
    config: DecidePortConfig | None = None,
    *,
    llm: LLM | None = None,
    usage_sink: Callable[[SteeringLlmCall], None] | None = None,
    spend_guard: SpendGuard | None = None,
    clock: Clock | None = None,
) -> DecidePort:
    """Materialise the DecidePort the conduct loop talks to.

    None or the `in_memory` substrate returns an `InMemoryDecidePort` (the
    default + test convenience). `grid_walk` returns a `GridWalkDecidePort`
    at the configured resolution. `sobol` / `botorch` return the seeder /
    GP brain (both probe the optional `bo` dependency at construction, raising
    `ValueError` if it is missing). `staged` composes a Sobol seeder + a
    BoTorch brain into the two-phase composite. `llm` returns an
    `LlmDecidePort` steered by the injected `llm` port, raising `ValueError`
    if `llm` is None (mirroring the `bo`-missing guard: a config error surfaces
    at construction, mapping to HTTP 422 before any FSM transition). Other arms
    ignore the `llm` argument. New arms are added here as they are earned,
    exactly as `build_compute_port` grew its `local_process` arm.
    """
    resolved = config if config is not None else DecidePortConfig()
    if resolved.substrate == "in_memory":
        return InMemoryDecidePort()
    if resolved.substrate == "grid_walk":
        return GridWalkDecidePort(points_per_axis=resolved.points_per_axis)
    if resolved.substrate == "sobol":
        return SobolDecidePort()
    if resolved.substrate == "botorch":
        return _build_botorch(resolved)
    if resolved.substrate == "staged":
        return StagedDecidePort(
            seeder=SobolDecidePort(),
            brain=_build_botorch(resolved),
            threshold=resolved.staged_threshold,
            brain_min_observations=resolved.min_observations,
        )
    if resolved.substrate == "llm":
        if llm is None:
            raise ValueError(
                "the 'llm' decide substrate requires an llm port; "
                "pass build_decide_port(config, llm=deps.llm)"
            )
        return LlmDecidePort(
            llm=llm,
            usage_sink=usage_sink,
            spend_guard=spend_guard,
            spend_agent_id=resolved.spend_agent_id,
            clock=clock,
        )
    raise ValueError(  # pragma: no cover
        f"unsupported decide substrate: {resolved.substrate!r}"
    )


def _build_botorch(config: DecidePortConfig) -> BoTorchDecidePort:
    """Construct the BoTorch brain from config (shared by the botorch + staged arms)."""
    return BoTorchDecidePort(
        min_observations=config.min_observations,
        num_restarts=config.num_restarts,
        raw_samples=config.raw_samples,
        seed=config.seed,
    )


__all__ = [
    "DecidePortConfig",
    "DecideSubstrate",
    "WireDecideSubstrate",
    "build_decide_port",
]
