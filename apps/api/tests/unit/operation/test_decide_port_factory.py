"""Factory exhaustiveness for build_decide_port over DecideSubstrate.

`build_decide_port` dispatches on the `DecideSubstrate` Literal with an
if-chain ending in a `# pragma: no cover` ValueError. Adding a substrate to
the Literal without adding its factory arm would otherwise fail only at
deployment (the un-routed substrate hits the final raise). This test pins the
two sets together: every `DecideSubstrate` member must build a `DecidePort`,
and the wire-selectable subset must be a subset of the full set.
"""

from __future__ import annotations

import typing

import pytest

from cora.operation.adapters.decide_port_config import (
    DecidePortConfig,
    DecideSubstrate,
    WireDecideSubstrate,
    build_decide_port,
)
from cora.operation.ports.decide_port import DecidePort

_TORCH_SUBSTRATES = {"sobol", "botorch", "staged"}
_ALL_SUBSTRATES = typing.get_args(DecideSubstrate)


@pytest.mark.parametrize("substrate", _ALL_SUBSTRATES)
def test_build_decide_port_routes_every_substrate(substrate: str) -> None:
    """Every DecideSubstrate member builds a DecidePort (no un-routed arm)."""
    if substrate in _TORCH_SUBSTRATES:
        pytest.importorskip("botorch", reason=f"{substrate!r} needs the optional 'bo' extra")
    # Keep the staged threshold consistent with its brain floor (default 5).
    port = build_decide_port(DecidePortConfig(substrate=substrate))  # type: ignore[arg-type]
    assert isinstance(port, DecidePort)


def test_wire_substrates_are_a_subset_of_all_substrates() -> None:
    """The wire-selectable set never drifts outside the factory-buildable set."""
    wire = set(typing.get_args(WireDecideSubstrate))
    all_substrates = set(_ALL_SUBSTRATES)
    assert wire <= all_substrates


def test_torch_substrates_are_not_wire_selectable() -> None:
    """The heavy GP/BO arms stay off the wire until they have a designed wire config."""
    wire = set(typing.get_args(WireDecideSubstrate))
    assert wire.isdisjoint(_TORCH_SUBSTRATES)
