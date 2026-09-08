"""Architecture fitness: DecidingBrainRef admits exactly the brains that decide.

`cora.shared.steering.DecidingBrainRef` is the typed identity of the brain that
answered one iteration, and `decider_replayability.SUBSTRATE_REPLAYABILITY`
classifies each substrate by whether re-asking it reproduces its advice. The
two make the same claim about `staged` from opposite directions: the map calls
it DELEGATED (it records no ref of its own), and the type refuses to construct
it. That agreement is load-bearing rather than cosmetic, because a composite
that grew an identity would misclassify every run it decided, so it is checked
here instead of restated in two docstrings.

Ranges over the classification map, not over a hand-written list of
substrates: the map is kept equal to the factory's own `DecideSubstrate`
Literal in both directions by `test_decider_replayability`, so a seventh
substrate reaches these assertions without anyone remembering to add it.
"""

import pytest

from cora.operation.adapters.decider_replayability import (
    SUBSTRATE_REPLAYABILITY,
    Replayability,
    replayability_of,
)
from cora.shared.steering import (
    DecidingBrainRef,
    InvalidDecidingBrainRefError,
    SteeringSubstrate,
)

_DECIDING = sorted(
    substrate
    for substrate, replayability in SUBSTRATE_REPLAYABILITY.items()
    if replayability is not Replayability.DELEGATED
)
_DELEGATED = sorted(
    substrate
    for substrate, replayability in SUBSTRATE_REPLAYABILITY.items()
    if replayability is Replayability.DELEGATED
)


def _brain(substrate: str) -> DecidingBrainRef:
    """The brain an adapter on `substrate` would record, minimally populated."""
    if substrate == SteeringSubstrate.LLM:
        return DecidingBrainRef(
            substrate=SteeringSubstrate.LLM, provider="anthropic", model="claude-sonnet-4-6"
        )
    return DecidingBrainRef(substrate=SteeringSubstrate(substrate))


@pytest.mark.architecture
def test_the_two_classes_of_substrate_are_both_non_empty() -> None:
    """Guard the guards: an empty split would make both tests below vacuous.

    `_DECIDING` and `_DELEGATED` are derived by filtering one map, so a
    refactor that emptied either (renaming the enum member, dropping the
    DELEGATED class) would leave a parametrized test with zero cases and a
    green suite that checked nothing.
    """
    assert _DECIDING, "no substrate classifies as deciding; the split lost its subject"
    assert _DELEGATED, "no substrate classifies as DELEGATED; the staged guard has no subject"


@pytest.mark.architecture
@pytest.mark.parametrize("substrate", _DECIDING)
def test_a_deciding_substrate_is_constructible_and_classifies_by_its_own_ref(
    substrate: str,
) -> None:
    """A brain that decides can be named, and its flat form reads back the same.

    Ties the renderer to the reader across a module boundary.
    `str(DecidingBrainRef)` (in `cora.shared`) is the only producer of the flat
    `model_ref` an iteration records; `replayability_of` (in the adapter tier)
    is the reader that classifies it, and it parses rather than looks up. A
    substrate whose rendering spelled something the parser cannot place would
    raise here rather than reaching a run, where the ref would land on every
    iteration and only fail when some consumer tried to classify it.
    """
    brain = _brain(substrate)

    assert replayability_of(str(brain)) is SUBSTRATE_REPLAYABILITY[substrate]  # pyright: ignore[reportArgumentType]


@pytest.mark.architecture
@pytest.mark.parametrize("substrate", _DELEGATED)
def test_a_delegated_substrate_cannot_be_named_as_a_deciding_brain(substrate: str) -> None:
    """A composite records its child's identity, so it has none to record.

    The classifier already refuses to place a DELEGATED ref, which catches the
    defect at READ time on a row that was already written. This makes the same
    state unwritable, so the composite cannot record itself in the first place.
    """
    with pytest.raises(InvalidDecidingBrainRefError):
        DecidingBrainRef(substrate=SteeringSubstrate(substrate))
