"""Architecture fitness: keep SteeringBrain's variant map total over SteeringSubstrate.

`cora.shared.steering.BRAIN_TYPE_BY_SUBSTRATE` pairs every `SteeringSubstrate`
member with the `SteeringBrain` variant that records its determining config
(`GridWalkBrain`, `BoTorchBrain`, ...). The two are hand-maintained
independently: one is an enum literal added alongside a new
`build_decide_port` arm, the other a dataclass added alongside this module's
own vocabulary. This fitness pins them so a substrate added to
`SteeringSubstrate` without a matching `SteeringBrain` variant fails CI
before a design pin can silently drop that substrate's config, rather than
being discovered at export time. Mirrors
`test_steering_substrate_matches_decide_substrate_literal`, the sibling
fitness for `SteeringSubstrate` itself.
"""

import pytest

from cora.shared.steering import BRAIN_TYPE_BY_SUBSTRATE, SteeringSubstrate


@pytest.mark.architecture
def test_every_substrate_has_exactly_one_brain_variant() -> None:
    mapped = set(BRAIN_TYPE_BY_SUBSTRATE.keys())
    every_substrate = set(SteeringSubstrate)
    assert mapped == every_substrate, (
        f"BRAIN_TYPE_BY_SUBSTRATE covers {mapped} but SteeringSubstrate has "
        f"{every_substrate}. Add a SteeringBrain variant for the missing "
        "substrate (or remove the stale mapping entry) before either widens further."
    )


@pytest.mark.architecture
def test_no_two_substrates_share_a_brain_variant() -> None:
    variant_types = list(BRAIN_TYPE_BY_SUBSTRATE.values())
    assert len(variant_types) == len(set(variant_types)), (
        "Two SteeringSubstrate members map to the same SteeringBrain variant "
        "class. Each substrate's config is its own type, even an empty one "
        "(InMemoryBrain / SobolBrain), so a run's recorded brain type alone "
        "identifies which substrate decided it."
    )
