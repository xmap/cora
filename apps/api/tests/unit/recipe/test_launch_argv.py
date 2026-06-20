"""Unit tests for build_argv: vetted LaunchSpec + params -> injection-safe argv."""

import pytest

from cora.recipe.aggregates.method.launch_argv import (
    MissingLaunchParameterError,
    UnsafeLaunchUriError,
    build_argv,
)
from cora.recipe.aggregates.method.launch_spec import ArgStyle, LaunchArg, LaunchSpec

_SIRT = LaunchSpec(
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
def test_build_argv_renders_the_2bm_sirt_recon() -> None:
    argv = build_argv(
        _SIRT,
        {"algorithm": "sirt", "num_iter": 100, "center": 1023.5, "remove_stripe": True},
        input_uris=("file:///data/raw.h5",),
        output_uri="file:///data/recon.h5",
    )
    assert argv == (
        "python",
        "-m",
        "tomopy.recon.cli",
        "--algorithm",
        "sirt",
        "--num-iter",
        "100",
        "--center",
        "1023.5",
        "--remove-stripe",
        "--input",
        "file:///data/raw.h5",
        "--output",
        "file:///data/recon.h5",
    )


@pytest.mark.unit
def test_build_argv_omits_flag_only_when_false() -> None:
    argv = build_argv(
        _SIRT,
        {"algorithm": "sirt", "num_iter": 1, "center": 0, "remove_stripe": False},
    )
    assert "--remove-stripe" not in argv


@pytest.mark.unit
def test_build_argv_raises_for_missing_required_parameter() -> None:
    with pytest.raises(MissingLaunchParameterError):
        build_argv(_SIRT, {"algorithm": "sirt", "num_iter": 1})  # center missing


@pytest.mark.unit
def test_build_argv_renders_positional_args_by_position() -> None:
    spec = LaunchSpec(
        base_command=("tool",),
        args=(
            LaunchArg(name="second", position=1, required=True),
            LaunchArg(name="first", position=0, required=True),
        ),
    )
    assert build_argv(spec, {"first": "A", "second": "B"}) == ("tool", "A", "B")


@pytest.mark.unit
def test_build_argv_treats_malicious_value_as_one_inert_token() -> None:
    spec = LaunchSpec(
        base_command=("tool",), args=(LaunchArg(name="x", flag="--x", required=True),)
    )
    argv = build_argv(spec, {"x": "sirt; rm -rf /"})
    # the whole value is ONE argv token; no shell, no splitting.
    assert argv == ("tool", "--x", "sirt; rm -rf /")


@pytest.mark.unit
def test_build_argv_rejects_uri_with_control_character() -> None:
    spec = LaunchSpec(base_command=("tool",), input_arg="--in")
    with pytest.raises(UnsafeLaunchUriError):
        build_argv(spec, {}, input_uris=("file:///data\nrm.h5",))


@pytest.mark.unit
def test_build_argv_rejects_uri_with_disallowed_scheme() -> None:
    spec = LaunchSpec(base_command=("tool",), output_arg="--out")
    with pytest.raises(UnsafeLaunchUriError):
        build_argv(spec, {}, output_uri="ftp://evil/x.h5")


@pytest.mark.unit
def test_build_argv_appends_uris_positionally_when_no_io_flags() -> None:
    spec = LaunchSpec(base_command=("tool",))
    argv = build_argv(spec, {}, input_uris=("file:///in.h5",), output_uri="file:///out.h5")
    assert argv == ("tool", "file:///in.h5", "file:///out.h5")
