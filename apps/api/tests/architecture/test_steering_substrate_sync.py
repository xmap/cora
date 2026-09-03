"""Architecture fitness: keep SteeringSubstrate in sync with the DecideSubstrate Literal.

`cora.shared.steering.SteeringSubstrate` is a StrEnum mirror of
`cora.operation.adapters.decide_port_config.DecideSubstrate`, a Literal
of the full set of decider substrates `build_decide_port` can
materialise. The mirror exists because tach forbids `cora.shared` from
depending on `cora.operation.adapters` (the shared module is imported
by `cora.campaign`, which may not reach the adapter tier), so the
Procedure-event payload that will pin a steered run's brain selection
cannot type that field with the Literal itself. This fitness pins the
two value sets so a substrate added to one and not the other fails CI
at PR time rather than at export time.

Deliberately NOT compared against `WireDecideSubstrate`: that Literal
is the narrower, wire-selectable subset, and syncing against it would
make the enum forget every substrate that is factory-buildable but not
yet wire-selectable.
"""

from typing import get_args

import pytest

from cora.operation.adapters.decide_port_config import DecideSubstrate
from cora.shared.steering import SteeringSubstrate


@pytest.mark.architecture
def test_steering_substrate_matches_decide_substrate_literal() -> None:
    substrates = {member.value for member in SteeringSubstrate}
    literal_values = set(get_args(DecideSubstrate))
    assert substrates == literal_values, (
        f"SteeringSubstrate {substrates} and DecideSubstrate {literal_values} have drifted. "
        "Widen DecideSubstrate and its build_decide_port arm first, then SteeringSubstrate."
    )
