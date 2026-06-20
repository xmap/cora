"""build_argv: render a vetted LaunchSpec + validated parameters into argv.

The pure, injection-safe core that turns a Method's `launch_spec` plus a
Run's schema-validated `effective_parameters` (and caller-supplied
input/output URIs) into the argv tuple a compute job runs. No shell, no
templating: each value becomes exactly one `str(...)` token. Per
[[project-method-launch-spec-stage0-design]].

Render order (unambiguous): `base_command`, then flag-style args in
declared order, then positional args by ascending position, then each
input URI (prefixed by `input_arg` when set), then the output URI
(prefixed by `output_arg` when set).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from cora.recipe.aggregates.method.launch_spec import ArgStyle, LaunchSpec

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# Control characters (incl. NUL, newline, tab, DEL). A URI carrying one
# is rejected: it cannot be a legitimate file/s3/https locator and is the
# classic vector for smuggling extra tokens into downstream tools.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# v1 scheme allowlist. A URI is data location, not executable behavior;
# this closes obviously-wrong / dangerous schemes, NOT path authorization
# (a caller can still target any path within an allowed scheme).
_ALLOWED_URI_SCHEMES = ("file", "s3", "https")


class MissingLaunchParameterError(ValueError):
    """A required LaunchArg's parameter is absent from effective_parameters.

    The Run cannot satisfy the recipe. Surfaced as HTTP 422 by the conduct
    route (the run's params do not fulfil the chosen recipe).
    """

    def __init__(self, arg_name: str) -> None:
        super().__init__(f"launch parameter {arg_name!r} is required by the launch_spec but absent")
        self.arg_name = arg_name


class UnsafeLaunchUriError(ValueError):
    """A caller-supplied input/output URI is unsafe.

    Carries a control character or a scheme outside the allowlist.
    Surfaced as HTTP 422 by the conduct route.
    """

    def __init__(self, uri: str, reason: str) -> None:
        super().__init__(f"launch uri {uri!r} rejected: {reason}")
        self.uri = uri
        self.reason = reason


def _check_uri(uri: str) -> None:
    if _CONTROL_CHARS.search(uri):
        raise UnsafeLaunchUriError(uri, "contains a control character")
    scheme = uri.split("://", 1)[0].lower() if "://" in uri else ""
    if scheme not in _ALLOWED_URI_SCHEMES:
        raise UnsafeLaunchUriError(uri, f"scheme must be one of {', '.join(_ALLOWED_URI_SCHEMES)}")


def build_argv(
    launch_spec: LaunchSpec,
    effective_parameters: Mapping[str, Any],
    *,
    input_uris: Sequence[str] = (),
    output_uri: str | None = None,
) -> tuple[str, ...]:
    """Render `launch_spec` + `effective_parameters` (+ URIs) into argv.

    Raises `MissingLaunchParameterError` if a required arg's parameter is
    absent, and `UnsafeLaunchUriError` if a URI fails hygiene. A
    non-required absent arg is omitted (its flag does not appear). A
    `flag_only` arg emits its bare flag iff the value is truthy.
    """
    argv: list[str] = list(launch_spec.base_command)

    for arg in (a for a in launch_spec.args if a.flag is not None):
        if arg.name not in effective_parameters:
            if arg.required:
                raise MissingLaunchParameterError(arg.name)
            continue
        value = effective_parameters[arg.name]
        if arg.style is ArgStyle.FLAG_ONLY:
            if value:
                argv.append(arg.flag)  # type: ignore[arg-type]  # flag is not None in this branch
        else:
            argv.extend([arg.flag, str(value)])  # type: ignore[list-item]

    for arg in sorted(
        (a for a in launch_spec.args if a.position is not None),
        key=lambda a: a.position or 0,
    ):
        if arg.name not in effective_parameters:
            if arg.required:
                raise MissingLaunchParameterError(arg.name)
            continue
        argv.append(str(effective_parameters[arg.name]))

    for uri in input_uris:
        _check_uri(uri)
        if launch_spec.input_arg is not None:
            argv.append(launch_spec.input_arg)
        argv.append(uri)

    if output_uri is not None:
        _check_uri(output_uri)
        if launch_spec.output_arg is not None:
            argv.append(launch_spec.output_arg)
        argv.append(output_uri)

    return tuple(argv)


__all__ = [
    "MissingLaunchParameterError",
    "UnsafeLaunchUriError",
    "build_argv",
]
