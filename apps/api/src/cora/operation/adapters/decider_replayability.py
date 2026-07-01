"""Replayability classification of decider brains by their `model_ref`.

The `conduct_until_advised` loop records, per iteration, the `model_ref` of the
brain that decided it (on `ProcedureIterationEnded`). The loop's replay-
determinism property holds only when that brain is a PURE FUNCTION of the
evidence: a replay re-asks the brain and must get the same answer. Some brains
satisfy this (the grid walker, the Sobol seeder, the in-memory fake); a GP
Bayesian-optimization brain does not, because its fit + acquisition are not
bit-reproducible across BLAS / threading / hardware / library versions even
with a fixed seed.

This module makes that distinction EXPLICIT and machine-checkable rather than
leaving it as prose. `is_replay_safe(model_ref)` answers whether a run whose
iterations carry that `model_ref` can be faithfully replayed by re-asking the
brain. A consumer that replays or resumes a steered run consults it to refuse
(or flag) a run that a non-deterministic brain decided, instead of silently
re-deriving a divergent history.

## Why a classifier, not a per-run event flag (yet)

The deciding brain is already on the stream (`ProcedureIterationEnded.
model_ref`), so a steered run's replay-safety is derivable from data already
recorded; no new event field or loop change is needed to MARK a run. The
recorded-decision leg that would make a non-deterministic brain itself
replayable (record the advised next_point and re-seed it instead of re-asking)
is the separate, deferred build, earned when a GP-steered run must actually be
replayed or resumed. Until then this classifier is how a consumer tells the two
classes of run apart.

## Keep this in lockstep with the deciders

Every decider's `_MODEL_REF` constant must appear in exactly one of the two
sets below. A fitness test asserts the union covers every shipped decider's
`model_ref`, so adding a decider without classifying it fails CI rather than
defaulting to a silent (and possibly wrong) replay-safety assumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_REPLAY_SAFE_MODEL_REFS = frozenset(
    {
        "in_memory",  # the deterministic fake: advice is seeded by iteration index
        "grid_walk",  # pure function of space + observation count
        "sobol",  # unscrambled Sobol: pure function of space + draw index
    }
)
"""`model_ref`s whose advice is a pure function of the evidence.

A run decided entirely by these brains replays faithfully by re-asking the
brain, so it carries the conduct loop's replay-determinism property.
"""

_FORWARD_ONLY_MODEL_REFS = frozenset(
    {
        "botorch",  # GP fit + acquisition: not bit-reproducible across environments
    }
)
"""`model_ref`s whose advice is NOT bit-reproducible on RE-ASK.

"forward-only" here means NOT re-ask-reproducible -- re-running the brain over
the same evidence may diverge (GP fit + acquisition are not bit-reproducible
across BLAS / threading / hardware / version). It is DISTINCT from "not
recorded": TIER-1 replay records the brain's advised_next_point on the
iteration event + surfaces it in the iteration projection, so a finished
GP-steered run IS reconstructable by READING the recorded trail. This set
stays as-is because the classifier judges the RE-ASK path (still unsafe); a
run is not reclassified replay-safe just because the decision is recorded.
Flipping a ref to replay-safe is earned only when a consumer RE-SEEDS the
recorded point on replay instead of re-asking (the deferred resume leg:
decide-loop resume entry + ValueCaptured channel).
"""

_CLASSIFIED_MODEL_REFS = _REPLAY_SAFE_MODEL_REFS | _FORWARD_ONLY_MODEL_REFS


def is_replay_safe(model_ref: str) -> bool:
    """True if a run decided by `model_ref` replays faithfully by re-asking.

    Raises `ValueError` for an unclassified `model_ref` so an unknown brain is
    a loud failure, never a silent assume-safe. The staged composite never
    appears here: it records the CHILD brain's `model_ref` on each iteration
    (it adds no `model_ref` of its own), so a staged run's iterations classify
    individually (its Sobol passes are safe, its BoTorch passes are not).
    """
    if model_ref not in _CLASSIFIED_MODEL_REFS:
        raise ValueError(
            f"unclassified decider model_ref {model_ref!r}; add it to "
            "_REPLAY_SAFE_MODEL_REFS or _FORWARD_ONLY_MODEL_REFS"
        )
    return model_ref in _REPLAY_SAFE_MODEL_REFS


def run_is_replay_safe(model_refs: Iterable[str | None]) -> bool:
    """True if EVERY iteration's `model_ref` in a run is replay-safe.

    `model_refs` is the collection of per-iteration `model_ref` values a run
    recorded (None entries, from non-steered or verdict-less iterations, are
    ignored). A run is replay-safe only if no iteration was decided by a
    forward-only brain, so a staged run that reached its BoTorch phase is
    correctly non-replayable while one that stopped during Sobol seeding is
    safe.
    """
    return all(is_replay_safe(ref) for ref in model_refs if ref is not None)


__all__ = [
    "is_replay_safe",
    "run_is_replay_safe",
]
