"""Replayability classification of decider brains by their `model_ref`.

The `conduct_until_advised` loop records, per iteration, the `model_ref` of the
brain that decided it (on `ProcedureIterationEnded`). The loop's replay-
determinism property holds only when that brain is a PURE FUNCTION of the
evidence: a replay re-asks the brain and must get the same answer. Some brains
satisfy this (the grid walker, the Sobol seeder, the in-memory fake); a GP
Bayesian-optimization brain does not, because its fit + acquisition are not
bit-reproducible across BLAS / threading / hardware / library versions even
with a fixed seed, and neither does an LLM brain, whose provider may resample
or move the model under an unpinned snapshot.

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
recorded-decision leg that makes a non-deterministic brain RESUMABLE (record
each pass's advised next_point + measured outcome, then re-seed the brain from
that record instead of re-asking) is now SHIPPED: `conduct_until_advised_from`
re-conditions the brain from the recorded (x, y) history and consults it live
only at the open frontier. That does NOT reclassify a GP run as replay-safe:
this classifier still judges the RE-ASK path (re-running the brain over the same
evidence), which stays non-reproducible for a GP. Resume side-steps the re-ask
entirely by replaying the recorded points, so "forward-only" (not
re-ask-reproducible) and "resumable" (re-seed-from-record) are now BOTH true of
a GP run at once. This classifier remains how a consumer that RE-ASKS tells the
two classes apart.

## What the coverage guard ranges over, and why it is the factory's Literal

`SUBSTRATE_REPLAYABILITY` below is keyed by `DecideSubstrate`, the Literal that
`decide_port_config` maintains as the set of substrates its factory can build.
That list is the INDEPENDENT side of the check: it is edited for a different
reason (making an adapter buildable) by whoever adds an adapter, and a
substrate that is not in it cannot be constructed at all. The fitness test
asserts the two sets are equal in BOTH directions, so adding a seventh
substrate fails CI until it is classified, and deleting one fails until its
classification goes too.

The guard this replaces did not have an independent side. It asserted a
hand-written literal set of four refs against the classifier's own hand-written
sets, so it agreed by construction, and it never ranged over the adapters at
all. It reported nothing while the `llm` substrate shipped a `model_ref` that
no set could ever contain.

## Substrate name is not the same thing as recorded ref

Four substrates record their own name verbatim, so their recorded ref and their
substrate key coincide. Two do not:

  - `staged` records NO ref of its own. It returns the child brain's advice
    unchanged, so what lands on the iteration is `sobol` or `botorch`. Its
    classification is `DELEGATED`, and seeing the literal string `"staged"` on
    an iteration means the composite grew a ref it should not have, which is
    why that input raises rather than classifying.
  - `llm` records `f"{provider}:{model}"`, so its recorded refs are an open set
    (one per model ever configured) rather than a single constant. A ref
    carrying a colon is read as this form; substrate names are bare
    identifiers and never carry one.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from cora.operation.adapters.decide_port_config import DecideSubstrate


class Replayability(StrEnum):
    """How a decider substrate behaves when its advice is RE-ASKED."""

    REPLAY_SAFE = "replay_safe"
    """Advice is a pure function of the evidence, so a re-ask reproduces it."""

    FORWARD_ONLY = "forward_only"
    """Advice is not bit-reproducible on re-ask.

    DISTINCT from "not recorded" AND from "not resumable": the iteration event
    records the brain's advised_next_point and the projection surfaces it, so a
    finished run IS reconstructable by READING the recorded trail, and
    `conduct_until_advised_from` RESUMES such a run by re-seeding the brain from
    the recorded (x, y) history. A substrate stays in this class regardless: the
    classifier judges the RE-ASK path. A run is not reclassified replay-safe
    because its decisions are recorded or because it can be resumed. Moving a
    substrate out of this class would require the RE-ASK itself to become
    bit-reproducible.
    """

    DELEGATED = "delegated"
    """Records no ref of its own; the child brain's ref is what lands.

    A composite. Its runs classify per iteration by whichever child decided
    each one, so the composite's own name never reaches `is_replay_safe`.
    """


SUBSTRATE_REPLAYABILITY: Final[Mapping[DecideSubstrate, Replayability]] = {
    "in_memory": Replayability.REPLAY_SAFE,
    "grid_walk": Replayability.REPLAY_SAFE,
    "sobol": Replayability.REPLAY_SAFE,
    "botorch": Replayability.FORWARD_ONLY,
    "staged": Replayability.DELEGATED,
    "llm": Replayability.FORWARD_ONLY,
}
"""Every substrate `build_decide_port` can materialise, with its replayability.

`in_memory` is seeded by iteration index, `grid_walk` is a pure function of
space + observation count, and unscrambled `sobol` is a pure function of space
+ draw index, so all three reproduce on re-ask. `botorch` does not: GP fit +
acquisition are not bit-reproducible across BLAS / threading / hardware /
version. Neither does `llm`: the provider may sample, and an unpinned snapshot
may move the model under a caller who never changed a line. `staged` records no
ref of its own.

Kept equal to `DecideSubstrate` in both directions by
`tests/unit/operation/test_decider_replayability.py`.
"""

_LLM_REF_SEPARATOR = ":"


def _is_llm_ref(model_ref: str) -> bool:
    """True if `model_ref` has the `llm` substrate's `provider:model` shape.

    Partitions on the FIRST separator only: a provider's model identifier may
    itself carry one (`ollama:llama3:8b`), and everything after the provider is
    the model. A half-empty ref (`anthropic:` or `:claude-sonnet-4-6`) is NOT
    this shape, so it falls through to the unclassified branch and raises
    rather than being read as a nameless model.
    """
    provider, _, model = model_ref.partition(_LLM_REF_SEPARATOR)
    return bool(provider) and bool(model)


def replayability_of(model_ref: str) -> Replayability:
    """The `Replayability` of the brain that recorded `model_ref`.

    Raises `ValueError` for a ref this module cannot place, so an unknown brain
    is a loud failure and never a silent assume-safe. `DELEGATED` substrates
    raise too: a composite records its child's ref, so its own name appearing on
    an iteration is a defect in the composite rather than a classifiable run.
    """
    if _is_llm_ref(model_ref):
        return SUBSTRATE_REPLAYABILITY["llm"]

    replayability = SUBSTRATE_REPLAYABILITY.get(model_ref)  # pyright: ignore[reportArgumentType]
    if replayability is None:
        raise ValueError(
            f"unclassified decider model_ref {model_ref!r}; add its substrate to "
            "SUBSTRATE_REPLAYABILITY"
        )
    if replayability is Replayability.DELEGATED:
        raise ValueError(
            f"decider model_ref {model_ref!r} names a composite substrate, which "
            "records its child brain's ref rather than its own; an iteration "
            "carrying it means the composite grew a ref it should not have"
        )
    return replayability


def is_replay_safe(model_ref: str) -> bool:
    """True if a run decided by `model_ref` replays faithfully by re-asking.

    Raises `ValueError` for a ref `replayability_of` cannot place.
    """
    return replayability_of(model_ref) is Replayability.REPLAY_SAFE


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
    "SUBSTRATE_REPLAYABILITY",
    "Replayability",
    "is_replay_safe",
    "replayability_of",
    "run_is_replay_safe",
]
