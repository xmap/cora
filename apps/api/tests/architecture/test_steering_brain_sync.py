# pyright: reportPrivateUsage=false
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

from typing import get_args

import pytest

from cora.operation._conduct_preparation import _brain_from_config
from cora.operation.adapters.decide_port_config import DecidePortConfig, DecideSubstrate
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
        "(InMemoryBrain / SobolBrain), so an IN-MEMORY brain value names the "
        "substrate that produced it without a separate tag. That holds for the "
        "Python object only: `serialize_brain` renders both empty variants as "
        "`{}`, so a STORED or EXPORTED row is disambiguated by its sibling "
        "`substrate` field, which is why `deserialize_brain` takes the "
        "substrate as a parameter rather than reading a tag back out."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("substrate", get_args(DecideSubstrate))
def test_the_projection_builds_the_variant_the_map_declares(substrate: str) -> None:
    """`_brain_from_config` must agree with `BRAIN_TYPE_BY_SUBSTRATE`.

    Without this the map is inert. `_brain_from_config` hand-writes its own
    substrate-to-variant match, so a mispairing (`case "sobol": return
    InMemoryBrain()`) type-checks, passes every round-trip test that only
    asserts the value it was handed, and leaves the map governing nothing
    at runtime -- the same shape as the `model_ref` parameter nothing
    passed, which the first commit of this arc existed to close.

    Ranges over `DecideSubstrate`, the factory's own Literal, rather than
    over the map's keys: that is the INDEPENDENT side, edited by whoever
    adds an adapter for a reason unrelated to this table, so a substrate
    that becomes buildable without a variant fails here rather than
    agreeing with itself. Mirrors the same choice in
    `decider_replayability`'s coverage guard.
    """
    config = DecidePortConfig(substrate=substrate)  # type: ignore[arg-type]

    built = _brain_from_config(config)

    assert type(built) is BRAIN_TYPE_BY_SUBSTRATE[SteeringSubstrate(substrate)]
