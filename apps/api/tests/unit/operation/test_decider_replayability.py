"""Replayability classification of decider brains.

Pins the explicit forward-only-vs-replay-safe boundary for GP-steered and
LLM-steered runs: the pure-function brains are replay-safe, BoTorch and the LLM
brain are forward-only, the staged composite classifies through its children
rather than under its own name, an unknown ref is a loud failure, and a run
classifies by the worst of its per-iteration model_refs.

The coverage guard ranges over `DecideSubstrate`, the factory's own Literal,
which is the independent side: it is maintained for a different reason (which
adapters `build_decide_port` can construct) than the classification is, and a
substrate absent from it cannot be built at all. The guard this replaces
asserted a hand-written set of four refs against the classifier's own
hand-written sets, so it agreed by construction and never saw the `llm`
substrate at all.
"""

from __future__ import annotations

from typing import get_args

import pytest

from cora.operation.adapters.decide_port_config import DecideSubstrate
from cora.operation.adapters.decider_replayability import (
    SUBSTRATE_REPLAYABILITY,
    Replayability,
    is_replay_safe,
    replayability_of,
    run_is_replay_safe,
)

_LLM_REF = "anthropic:claude-sonnet-4-6"


@pytest.mark.parametrize("model_ref", ["in_memory", "grid_walk", "sobol"])
def test_pure_function_brains_are_replay_safe(model_ref: str) -> None:
    assert is_replay_safe(model_ref) is True


def test_botorch_is_forward_only() -> None:
    assert is_replay_safe("botorch") is False


def test_an_llm_ref_is_forward_only() -> None:
    assert is_replay_safe(_LLM_REF) is False


def test_an_unrecognised_provider_still_routes_through_the_llm_branch() -> None:
    """There is no provider registry: the SHAPE of the ref is what routes it.

    Asserting against `SUBSTRATE_REPLAYABILITY["llm"]` instead would prove
    nothing, because `botorch` carries the same replayability and the
    comparison would hold whichever of the two it routed to.
    """
    assert replayability_of("nosuchprovider:nosuchmodel") is Replayability.FORWARD_ONLY


def test_an_llm_ref_whose_model_carries_a_separator_still_classifies() -> None:
    """`ollama:llama3:8b`: only the first separator splits provider from model."""
    assert is_replay_safe("ollama:llama3:8b") is False


@pytest.mark.parametrize("model_ref", [":claude-sonnet-4-6", "anthropic:"])
def test_a_half_empty_llm_ref_is_not_read_as_an_llm_ref(model_ref: str) -> None:
    with pytest.raises(ValueError, match="unclassified decider model_ref"):
        is_replay_safe(model_ref)


def test_unclassified_model_ref_raises() -> None:
    with pytest.raises(ValueError, match="unclassified decider model_ref"):
        is_replay_safe("mystery_brain")


def test_the_staged_composite_name_raises_rather_than_classifying() -> None:
    """It records its child's ref, so its own name on an iteration is a defect."""
    with pytest.raises(ValueError, match="names a composite substrate"):
        is_replay_safe("staged")


def test_run_with_all_pure_iterations_is_replay_safe() -> None:
    assert run_is_replay_safe(["sobol", "sobol", "grid_walk", None]) is True


def test_run_not_replay_safe_when_any_iteration_forward_only() -> None:
    # A staged run that reached its BoTorch phase: Sobol seed passes then GP.
    assert run_is_replay_safe(["sobol", "sobol", "botorch"]) is False


def test_run_not_replay_safe_when_any_iteration_was_llm_decided() -> None:
    assert run_is_replay_safe(["sobol", _LLM_REF]) is False


def test_run_replay_safe_ignores_none_entries() -> None:
    assert run_is_replay_safe([None, None]) is True


def test_every_buildable_substrate_is_classified() -> None:
    """Lockstep guard: `SUBSTRATE_REPLAYABILITY` covers every buildable substrate.

    Adding an arm to `DecideSubstrate` without classifying it should fail here
    rather than default to a silent (and possibly wrong) replay-safety
    assumption.
    """
    assert set(SUBSTRATE_REPLAYABILITY) == set(get_args(DecideSubstrate))


def test_no_classification_names_a_substrate_the_factory_cannot_build() -> None:
    """The other direction: a deleted substrate must lose its classification.

    Without this arm the guard would pass while `SUBSTRATE_REPLAYABILITY` kept a
    stale entry, and `is_replay_safe` would keep answering for a brain that no
    longer ships.
    """
    stale = set(SUBSTRATE_REPLAYABILITY) - set(get_args(DecideSubstrate))
    assert stale == set(), f"classified substrates the factory cannot build: {sorted(stale)}"


def test_exactly_one_substrate_delegates() -> None:
    """`replayability_of` refuses DELEGATED names, so the set must stay known.

    A second composite would need its own refusal reasoning rather than
    inheriting staged's, so this pins the count until that is thought through.
    """
    delegated = {
        substrate
        for substrate, replayability in SUBSTRATE_REPLAYABILITY.items()
        if replayability is Replayability.DELEGATED
    }
    assert delegated == {"staged"}
