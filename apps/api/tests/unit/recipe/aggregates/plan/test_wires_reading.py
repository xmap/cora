"""Unit tests for `constituents_from_wires`.

Pins the constituent-resolution rule: a pseudoaxis's constituents are the
`source_asset_id`s of the Plan wires whose `target` is that pseudoaxis,
ordered by `(target_port_name, source_asset_id)`, filtering out wires that
target anything else.
"""

from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.plan import Plan, PlanName, Wire, constituents_from_wires


def _plan(wires: frozenset[Wire], asset_ids: frozenset[UUID]) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("wiring test"),
        practice_id=uuid4(),
        asset_ids=asset_ids,
        wires=wires,
    )


@pytest.mark.unit
def test_constituents_from_wires_single_constituent_returns_the_one_source() -> None:
    pseudoaxis = uuid4()
    motor = uuid4()
    plan = _plan(
        frozenset({Wire(motor, "feedback_out", pseudoaxis, "constituent_in")}),
        frozenset({pseudoaxis, motor}),
    )
    assert constituents_from_wires(plan, pseudoaxis) == (motor,)


@pytest.mark.unit
def test_constituents_from_wires_orders_multi_constituent_by_target_port_name() -> None:
    pseudoaxis = uuid4()
    motor_a = uuid4()
    motor_b = uuid4()
    # Inserted out of order; the result must follow the target input-port
    # name (constituent_in_0 before constituent_in_1), not insertion order.
    plan = _plan(
        frozenset(
            {
                Wire(motor_b, "out", pseudoaxis, "constituent_in_1"),
                Wire(motor_a, "out", pseudoaxis, "constituent_in_0"),
            }
        ),
        frozenset({pseudoaxis, motor_a, motor_b}),
    )
    assert constituents_from_wires(plan, pseudoaxis) == (motor_a, motor_b)


@pytest.mark.unit
def test_constituents_from_wires_filters_out_wires_targeting_other_assets() -> None:
    pseudoaxis = uuid4()
    other_pseudoaxis = uuid4()
    motor = uuid4()
    # A fan-out source (motor) wired to two different targets; only the wire
    # whose target is `pseudoaxis` counts for `pseudoaxis`.
    plan = _plan(
        frozenset(
            {
                Wire(motor, "out", pseudoaxis, "constituent_in"),
                Wire(motor, "out", other_pseudoaxis, "constituent_in"),
                Wire(uuid4(), "out", other_pseudoaxis, "constituent_in_2"),
            }
        ),
        frozenset({pseudoaxis, other_pseudoaxis, motor}),
    )
    assert constituents_from_wires(plan, pseudoaxis) == (motor,)


@pytest.mark.unit
def test_constituents_from_wires_returns_empty_when_no_wire_targets_the_axis() -> None:
    plan = _plan(frozenset(), frozenset({uuid4()}))
    assert constituents_from_wires(plan, uuid4()) == ()
