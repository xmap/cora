"""Operation-side behaviour of the `SteeringRef` value-kind (W1 of the steering wire).

`SteeringRef` is the recipe value-kind that marks a `SetpointStep` value as
LOOP-SEEDED: the decide loop seeds the brain-advised coordinate into the
per-conduct `captures` dict before the pass runs, and the Conductor resolves the
ref against that dict exactly like a `CaptureRef`. These tests cover the
Operation side:

  - the Conductor resolves a `SteeringRef` setpoint from seeded captures
  - an UNSEEDED `SteeringRef` setpoint loud-fails (recorded, nothing written)
  - a `SteeringRef` setpoint round-trips through the pinned step payload
  - `expand` passes a `SteeringRef` through, and the determinism-hash wire form
    encodes it (a raw ref would crash `canonical_json_bytes`)
  - `conduct_until_advised` drives a `SteeringRef` block end-to-end (the wire
    guard accepts SteeringRef coverage and the loop seeds + resolves it)
"""

from uuid import uuid4

import pytest

from cora.operation._recipe_expansion import canonical_json_bytes, expand, steps_to_wire
from cora.operation.adapters.in_memory_compute_port import InMemoryComputePort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_decide_port import InMemoryDecidePort
from cora.operation.conductor import (
    ComputeStep,
    SetpointStep,
    step_to_payload,
    steps_from_payload,
)
from cora.operation.ports.decide_port import SteeringAdvice, SteeringVerdict
from cora.recipe.aggregates.recipe.body import RecipeSetpointStep, SteeringRef
from tests.unit.operation._helpers import (
    MOTOR_ADDR as _MOTOR_ADDR,
)
from tests.unit.operation._helpers import (
    OBJECTIVE_NAME as _OBJECTIVE_NAME,
)
from tests.unit.operation._helpers import (
    Transcript as _Transcript,
)
from tests.unit.operation._helpers import (
    build_conductor as _conductor,
)
from tests.unit.operation._helpers import (
    objective as _objective,
)
from tests.unit.operation._helpers import (
    objective_measurement as _objective_measurement,
)
from tests.unit.operation._helpers import (
    point_to_captures as _point_to_captures,
)
from tests.unit.operation._helpers import (
    space as _space,
)


def _steering_block() -> tuple[object, ...]:
    """A steered pass authored with a SteeringRef (the wire form), not a CaptureRef.

    The ComputeStep deposits the objective; the SetpointStep moves the steering
    axis via a SteeringRef, which the decide loop seeds before each pass.
    """
    return (
        ComputeStep(
            command=("solver", "metric"),
            input_uris=("file:///a.h5",),
            output_uri=None,
            parameters={},
            capture_name=_OBJECTIVE_NAME,
        ),
        SetpointStep(address=_MOTOR_ADDR, value=SteeringRef(steering_axis_name=_MOTOR_ADDR)),
    )


@pytest.mark.unit
async def test_steering_ref_setpoint_resolves_from_seeded_captures() -> None:
    """A SteeringRef setpoint writes the value the loop seeded into captures."""
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    conductor = _conductor(_Transcript(), compute_port=InMemoryComputePort(), control_port=control)

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(
            SetpointStep(address=_MOTOR_ADDR, value=SteeringRef(steering_axis_name=_MOTOR_ADDR)),
        ),  # type: ignore[arg-type]
        captures={_MOTOR_ADDR: 3.0},
    )

    assert result.succeeded is True
    assert (await control.read(_MOTOR_ADDR)).value == pytest.approx(3.0)


@pytest.mark.unit
async def test_unseeded_steering_ref_setpoint_loud_fails() -> None:
    """A SteeringRef whose axis was never seeded fails loud; nothing is written."""
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    conductor = _conductor(_Transcript(), compute_port=InMemoryComputePort(), control_port=control)

    result = await conductor.execute(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=(SetpointStep(address=_MOTOR_ADDR, value=SteeringRef(steering_axis_name="missing")),),  # type: ignore[arg-type]
        captures={},
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_class == "UnresolvedCaptureRef"


@pytest.mark.unit
def test_steering_ref_step_payload_round_trips() -> None:
    """A SteeringRef setpoint survives the pinned ResolvedStepsRecorded round-trip."""
    step = SetpointStep(address=_MOTOR_ADDR, value=SteeringRef(steering_axis_name=_MOTOR_ADDR))
    payload = step_to_payload(step)
    assert payload["value"] == {"__steering__": _MOTOR_ADDR}
    (rebuilt,) = steps_from_payload([payload])
    assert isinstance(rebuilt, SetpointStep)
    assert isinstance(rebuilt.value, SteeringRef)
    assert rebuilt.value.steering_axis_name == _MOTOR_ADDR


@pytest.mark.unit
def test_expand_passes_steering_ref_through_and_hash_form_encodes() -> None:
    """Expand carries a SteeringRef through; the determinism-hash wire form encodes it."""
    recipe_steps = (RecipeSetpointStep(address=_MOTOR_ADDR, value=SteeringRef("motor")),)
    expanded = expand(recipe_steps, {})
    head = expanded[0]
    assert isinstance(head, SetpointStep)
    assert isinstance(head.value, SteeringRef)
    assert head.value.steering_axis_name == "motor"
    # The hash wire form must encode the ref (a raw SteeringRef crashes the encoder).
    wire = steps_to_wire(expanded)
    assert wire[0]["value"] == {"__steering__": "motor"}
    canonical_json_bytes(wire)  # does not raise


@pytest.mark.unit
async def test_conduct_until_advised_drives_a_steering_ref_block() -> None:
    """conduct_until_advised accepts SteeringRef coverage and seeds + resolves it.

    The wire guard counts a SteeringRef setpoint as consuming its axis; pass 1
    seeds the probe (axis lower bound 0.0), the SetpointStep resolves it, and a
    first-turn Stop completes the Procedure.
    """
    transcript = _Transcript()
    control = InMemoryControlPort()
    control.simulate_connect(_MOTOR_ADDR)
    compute = InMemoryComputePort()
    compute.set_measurement_sequence(((_objective_measurement(2.0),),))
    brain = InMemoryDecidePort()
    brain.set_advice_sequence([SteeringAdvice(verdict=SteeringVerdict.STOP)])
    conductor = _conductor(transcript, compute_port=compute, control_port=control)

    result = await conductor.conduct_until_advised(
        procedure_id=uuid4(),
        principal_id=uuid4(),
        correlation_id=uuid4(),
        steps=_steering_block(),  # type: ignore[arg-type]
        decide_port=brain,
        objective=_objective(),
        space=_space(),
        objective_capture_name=_OBJECTIVE_NAME,
        point_to_captures=_point_to_captures,
    )

    assert result.succeeded is True
    assert transcript.events[-1] == "complete_procedure"
    # The probe (axis lower bound 0.0) seeded the SteeringRef setpoint.
    assert (await control.read(_MOTOR_ADDR)).value == pytest.approx(0.0)
