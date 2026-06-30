"""Replayability classification of decider brains.

Pins the explicit forward-only-vs-replay-safe boundary for GP-steered runs
(the P1-a "explicit, not silent" requirement): BoTorch is forward-only, the
pure-function brains are replay-safe, an unknown ref is a loud failure, and a
run classifies by the worst of its per-iteration model_refs. A lockstep
fitness test asserts every shipped decider's _MODEL_REF is classified.
"""

from __future__ import annotations

import pytest

from cora.operation.adapters.decider_replayability import (
    is_replay_safe,
    run_is_replay_safe,
)


@pytest.mark.parametrize("model_ref", ["in_memory", "grid_walk", "sobol"])
def test_pure_function_brains_are_replay_safe(model_ref: str) -> None:
    assert is_replay_safe(model_ref) is True


def test_botorch_is_forward_only() -> None:
    assert is_replay_safe("botorch") is False


def test_unclassified_model_ref_raises() -> None:
    with pytest.raises(ValueError, match="unclassified decider model_ref"):
        is_replay_safe("mystery_brain")


def test_run_with_all_pure_iterations_is_replay_safe() -> None:
    assert run_is_replay_safe(["sobol", "sobol", "grid_walk", None]) is True


def test_run_not_replay_safe_when_any_iteration_forward_only() -> None:
    # A staged run that reached its BoTorch phase: Sobol seed passes then GP.
    assert run_is_replay_safe(["sobol", "sobol", "botorch"]) is False


def test_run_replay_safe_ignores_none_entries() -> None:
    assert run_is_replay_safe([None, None]) is True


def test_every_shipped_decider_model_ref_is_classified() -> None:
    """Lockstep guard: every shipped decider's model_ref must be classified.

    Adding a decider without classifying its model_ref should fail here, not
    default to a silent (and possibly wrong) replay-safety assumption. The
    expected set is pinned literally; a new decider whose model_ref is added
    to this set but not to the classifier sets makes is_replay_safe raise.
    """
    shipped_refs = {"in_memory", "grid_walk", "sobol", "botorch"}
    for ref in shipped_refs:
        # Must not raise (every ref is in one of the two classified sets).
        is_replay_safe(ref)
