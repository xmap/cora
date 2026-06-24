"""Every `Step` union arm must round-trip through BOTH conduct serializers.

The arity / name-parity fitness tests (`test_conductor_step_kinds_match_procedure`,
`test_recipe_step_variants_match_step_union`) pin the type-level unions, but they
do NOT catch a missing SERIALIZER arm: a step kind can have a `Step` arm + a
`STEP_KIND_VALUES` entry yet still fall through to the trailing `check` branch in
`step_to_payload` / `_step_from_payload` (the resolved-steps pin driven on every
conduct via `_conduct_preparation`) or in `_expand._step_to_wire` (the
determinism / replay hash serializer). The first mis-serializes a step into a
`check` payload (AttributeErrors on `step.criterion` at resume); the second
SILENTLY mis-hashes the step as a check (breaks verify_steps_hash). Neither
raises at import or fails the arity gate.

This test round-trips one instance of EVERY non-check `Step` arm through both
serializers and asserts the result is the SAME arm it started as (never a
`CheckStep` and never the `"check"` wire kind), so a new arm without a matching
serializer arm fails here even though the arity gate stays green.
"""

from typing import get_args

import pytest

from cora.operation import conductor as _conductor_module
from cora.operation._recipe_expansion._expand import steps_to_wire
from cora.operation.conductor import (
    ActionStep,
    CaptureStep,
    CheckStep,
    ComputeStep,
    EqualsCriterion,
    SetpointStep,
    Step,
    step_to_payload,
    steps_from_payload,
)

# One representative instance per Step arm. The mapping is keyed by the arm
# class so a new union arm with no instance here trips the coverage assertion
# in `_instances_cover_every_arm` below.
_INSTANCES: dict[type, Step] = {
    SetpointStep: SetpointStep(address="2bma:rot:val", value=45.0, verify=True),
    ActionStep: ActionStep(name="collect", params={"repetitions": 3}),
    CheckStep: CheckStep(address="2bma:shutter", criterion=EqualsCriterion(expected=1)),
    CaptureStep: CaptureStep(address="2bma:sample:x", capture_name="home"),
    ComputeStep: ComputeStep(
        command=("tomopy", "find_center"),
        input_uris=("file:///a.h5", "file:///b.h5"),
        output_uri="file:///center.json",
        parameters={"algorithm": "vo"},
        capture_name="rotation_center_offset",
    ),
}

# A capture_name=None ComputeStep round-trips too (the field is additive +
# optional, slice 6c). Kept SEPARATE from `_INSTANCES` (which holds one
# representative per arm) so both the set + unset cases are exercised.
_COMPUTE_STEP_NO_CAPTURE = ComputeStep(
    command=("tomopy", "find_center"),
    input_uris=("file:///a.h5", "file:///b.h5"),
    output_uri="file:///center.json",
    parameters={"algorithm": "vo"},
    capture_name=None,
)

_CHECK_WIRE_KIND = "check"


def _instances_cover_every_arm() -> None:
    union_arms = set(get_args(_conductor_module.Step))
    instanced = set(_INSTANCES)
    missing = union_arms - instanced
    assert not missing, (
        f"_INSTANCES is missing a representative for Step arms "
        f"{sorted(a.__name__ for a in missing)}; add one so the serializer "
        f"round-trip covers every arm."
    )


@pytest.mark.architecture
def test_every_step_arm_round_trips_through_payload_serializer() -> None:
    """`step_to_payload` -> `_step_from_payload` reproduces every arm, none -> check.

    A missing arm in `step_to_payload` falls through to the trailing
    `check` branch (the resolved-steps pin then AttributeErrors on
    `step.criterion` at resume). Asserting exact equality per arm catches
    that: a non-check step that came back as a `CheckStep` is the bug.
    """
    _instances_cover_every_arm()
    for arm, instance in _INSTANCES.items():
        payload = step_to_payload(instance)
        (rebuilt,) = steps_from_payload([payload])
        assert type(rebuilt) is arm, (
            f"{arm.__name__} round-tripped through step_to_payload/_step_from_payload "
            f"as {type(rebuilt).__name__} (payload kind={payload.get('kind')!r}); a missing "
            f"serializer arm fell through to the check branch."
        )
        assert rebuilt == instance, f"{arm.__name__} did not round-trip value-identically."
        if arm is not CheckStep:
            assert payload["kind"] != _CHECK_WIRE_KIND, (
                f"{arm.__name__} serialized to a {_CHECK_WIRE_KIND!r} payload kind."
            )


@pytest.mark.architecture
def test_every_step_arm_round_trips_through_wire_serializer() -> None:
    """`steps_to_wire` emits a distinct wire kind for every arm, none -> check.

    A missing arm in the determinism / replay hash serializer
    (`_expand._step_to_wire`, driven via the public `steps_to_wire`)
    silently mis-hashes the step as a check, breaking verify_steps_hash
    with no exception. Asserting that every non-check arm emits a
    non-`check` wire kind catches the silent fall-through; running each
    instance through `steps_to_wire` exercises the real serializer arm.
    """
    _instances_cover_every_arm()
    for arm, instance in _INSTANCES.items():
        (wire,) = steps_to_wire((instance,))
        if arm is CheckStep:
            assert wire["kind"] == _CHECK_WIRE_KIND
        else:
            assert wire["kind"] != _CHECK_WIRE_KIND, (
                f"{arm.__name__} serialized to a {_CHECK_WIRE_KIND!r} wire kind via "
                f"steps_to_wire; the hash serializer is missing its arm."
            )
    # All wire kinds distinct across the full union so no two arms collide.
    all_kinds = [w["kind"] for w in steps_to_wire(tuple(_INSTANCES.values()))]
    assert len(set(all_kinds)) == len(_INSTANCES), (
        f"steps_to_wire emitted duplicate wire kinds {all_kinds}; two Step arms collide."
    )


@pytest.mark.architecture
def test_compute_step_capture_name_round_trips_both_serializers() -> None:
    """A ComputeStep `capture_name` (slice 6c) survives both serializers, set OR None.

    `_INSTANCES` covers the SET case (its ComputeStep carries a capture_name).
    This pins the UNSET case so a serializer that drops the field on None
    (folding it to a different wire shape than the set case) is caught.
    """
    with_capture = _INSTANCES[ComputeStep]
    assert isinstance(with_capture, ComputeStep)
    assert with_capture.capture_name == "rotation_center_offset"

    for instance in (with_capture, _COMPUTE_STEP_NO_CAPTURE):
        assert isinstance(instance, ComputeStep)
        # payload serializer round-trip
        (rebuilt,) = steps_from_payload([step_to_payload(instance)])
        assert rebuilt == instance, (
            f"ComputeStep(capture_name={instance.capture_name!r}) did not round-trip "
            f"through step_to_payload/_step_from_payload."
        )
        # hash/wire serializer carries the field (so the determinism hash splits
        # a capture_name-set step from a capture_name=None one)
        (wire,) = steps_to_wire((instance,))
        assert wire["capture_name"] == instance.capture_name
