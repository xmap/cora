"""Unit tests for the LaunchSpec value object + well-formedness validator."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.method.events import MethodVersioned
from cora.recipe.aggregates.method.evolver import evolve
from cora.recipe.aggregates.method.launch_spec import (
    ArgStyle,
    InvalidLaunchSpecError,
    LaunchArg,
    LaunchSpec,
    launch_spec_from_dict,
    launch_spec_to_dict,
    validate_launch_spec,
)
from cora.recipe.aggregates.method.state import Method, MethodName, MethodStatus


def _tomopy_spec() -> LaunchSpec:
    return LaunchSpec(
        base_command=("python", "-m", "tomopy.recon.cli"),
        args=(
            LaunchArg(name="algorithm", flag="--algorithm", required=True),
            LaunchArg(name="num_iter", flag="--num-iter", required=True),
            LaunchArg(name="center", flag="--center", required=True),
            LaunchArg(name="remove_stripe", flag="--remove-stripe", style=ArgStyle.FLAG_ONLY),
        ),
        input_arg="--input",
        output_arg="--output",
    )


@pytest.mark.unit
def test_argstyle_is_a_closed_two_value_enum() -> None:
    assert {s.value for s in ArgStyle} == {"value", "flag_only"}


@pytest.mark.unit
def test_well_formed_spec_passes() -> None:
    validate_launch_spec(_tomopy_spec())  # no raise


@pytest.mark.unit
def test_empty_base_command_rejected() -> None:
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(LaunchSpec(base_command=()))


@pytest.mark.unit
def test_empty_base_command_token_rejected() -> None:
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(LaunchSpec(base_command=("python", "")))


@pytest.mark.unit
def test_arg_with_both_flag_and_position_rejected() -> None:
    spec = LaunchSpec(base_command=("x",), args=(LaunchArg(name="a", flag="--a", position=0),))
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(spec)


@pytest.mark.unit
def test_arg_with_neither_flag_nor_position_rejected() -> None:
    spec = LaunchSpec(base_command=("x",), args=(LaunchArg(name="a"),))
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(spec)


@pytest.mark.unit
def test_bad_flag_syntax_rejected() -> None:
    spec = LaunchSpec(base_command=("x",), args=(LaunchArg(name="a", flag="not a flag"),))
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(spec)


@pytest.mark.unit
def test_flag_only_without_flag_rejected() -> None:
    spec = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="a", position=0, style=ArgStyle.FLAG_ONLY),),
    )
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(spec)


@pytest.mark.unit
def test_duplicate_arg_name_rejected() -> None:
    spec = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="a", flag="--a"), LaunchArg(name="a", flag="--b")),
    )
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(spec)


@pytest.mark.unit
def test_contiguous_positions_pass_but_gaps_rejected() -> None:
    ok = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="a", position=0), LaunchArg(name="b", position=1)),
    )
    validate_launch_spec(ok)  # no raise

    gapped = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="a", position=0), LaunchArg(name="b", position=2)),
    )
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(gapped)


@pytest.mark.unit
def test_bad_input_output_arg_rejected() -> None:
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(LaunchSpec(base_command=("x",), input_arg="bad arg"))
    with pytest.raises(InvalidLaunchSpecError):
        validate_launch_spec(LaunchSpec(base_command=("x",), output_arg="bad arg"))


@pytest.mark.unit
def test_to_dict_from_dict_round_trips_and_preserves_arg_order() -> None:
    spec = _tomopy_spec()
    data = launch_spec_to_dict(spec)
    # arg order is semantic: it must be preserved in the serialized form.
    assert [a["name"] for a in data["args"]] == ["algorithm", "num_iter", "center", "remove_stripe"]
    assert launch_spec_from_dict(data) == spec


@pytest.mark.unit
def test_to_dict_is_order_sensitive() -> None:
    a = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="a", flag="--a"), LaunchArg(name="b", flag="--b")),
    )
    b = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="b", flag="--b"), LaunchArg(name="a", flag="--a")),
    )
    assert launch_spec_to_dict(a) != launch_spec_to_dict(b)


# ---------- Method.content_subset + evolver participation (slice 2) ----------


@pytest.mark.unit
def test_method_content_subset_includes_launch_spec() -> None:
    spec = _tomopy_spec()
    m = Method(id=uuid4(), name=MethodName("recon"), launch_spec=spec)
    subset = m.content_subset()
    assert subset["launch_spec"] == launch_spec_to_dict(spec)


@pytest.mark.unit
def test_method_content_subset_renders_launch_spec_as_none_when_unset() -> None:
    m = Method(id=uuid4(), name=MethodName("recon"))
    assert m.content_subset()["launch_spec"] is None


@pytest.mark.unit
def test_method_content_subset_is_sensitive_to_launch_spec_arg_order() -> None:
    """Reordering args changes the content subset (hence the content_hash):
    arg order is argv order, the one non-sorted content-subset member."""
    a = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="p", flag="--p"), LaunchArg(name="q", flag="--q")),
    )
    b = LaunchSpec(
        base_command=("x",),
        args=(LaunchArg(name="q", flag="--q"), LaunchArg(name="p", flag="--p")),
    )
    mid = uuid4()
    ma = Method(id=mid, name=MethodName("m"), launch_spec=a)
    mb = Method(id=mid, name=MethodName("m"), launch_spec=b)
    assert ma.content_subset() != mb.content_subset()


@pytest.mark.unit
def test_evolver_preserves_launch_spec_across_versioned() -> None:
    spec = _tomopy_spec()
    prior = Method(
        id=uuid4(),
        name=MethodName("recon"),
        status=MethodStatus.DEFINED,
        launch_spec=spec,
    )
    evolved = evolve(
        prior,
        MethodVersioned(
            method_id=prior.id,
            version_tag="v1",
            content_hash=None,
            occurred_at=datetime(2026, 5, 10, tzinfo=UTC),
        ),
    )
    assert evolved.launch_spec == spec
