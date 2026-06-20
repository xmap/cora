"""LaunchSpec: a Method's vetted, injection-safe compute launch recipe.

Per [[project-method-launch-spec-stage0-design]]. A `LaunchSpec` pins
HOW a compute Method is launched (the argv) so a conduct caller selects
a registered recipe and supplies schema-validated parameters, instead
of POSTing a raw command. The command shape lives on the Method, where
it is reviewed, versioned, and content-hashed.

## Injection safety is a type fact

The vocabulary is CLOSED and carries NO interpolation strings:
- `base_command` is a tuple of LITERAL argv tokens (argv[0] can never
  be a placeholder, because there are no placeholders).
- each `LaunchArg` NAMES a key in the Method's `parameters_schema`; it
  never CONTAINS a template token. At conduct time the named value is
  rendered with `str(...)` into exactly ONE inert argv token.
- `ArgStyle` is a closed enum (`value` | `flag_only`). New styles only
  via rule-of-three + gate review; the style set is the seam where
  interpolation could creep back, so it stays small and typed.

There is therefore no template engine to exploit, and the executor
(`LocalProcessComputePort`) already runs argv-lists shell-free. A
malicious parameter value lands as one argv token, never as a second
command.

Naming note: the memo sketched the enum as `ArgRepr` with field `repr`;
implemented as `ArgStyle` with field `style` to avoid shadowing the
`repr` builtin (a lint smell). Same closed two-value vocabulary.

## Well-formedness vs cross-checks

`validate_launch_spec` here checks ONLY self-contained well-formedness
(non-empty literal base_command, flag/position XOR, flag syntax,
contiguous positions, flag_only-needs-a-flag, unique names). It does
NOT check that a `LaunchArg.name` exists in the owning Method's
`parameters_schema` (that cross-check belongs to the
`update_method_launch_spec` decider, which has the schema in hand) nor
that the schema key is boolean for `FLAG_ONLY` (same place).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# A flag is one short (`-c`) or long (`--num-iter`) option token. No
# spaces, no `=`, no value glued on: the value is a SEPARATE argv token
# rendered from the named parameter, never spliced into the flag.
_FLAG_RE = re.compile(r"^--?[A-Za-z0-9][A-Za-z0-9-]*$")


class InvalidLaunchSpecError(ValueError):
    """A LaunchSpec is malformed independent of any Method / schema.

    Raised by `validate_launch_spec` and surfaced as HTTP 422 by the
    `update_method_launch_spec` route's validation handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid launch spec: {reason}")
        self.reason = reason


class ArgStyle(StrEnum):
    """Closed v1 vocabulary for how a named parameter renders into argv."""

    VALUE = "value"
    """Emit the value as a token: `[flag, str(value)]` in flag mode, or
    `[str(value)]` in positional mode. The common case (`--num-iter 100`)."""

    FLAG_ONLY = "flag_only"
    """Boolean switch: emit `[flag]` iff the value is truthy, else nothing
    (`--remove-stripe` present or absent). Requires a flag (never
    positional) and a boolean schema key (checked at the slice)."""


@dataclass(frozen=True)
class LaunchArg:
    """One binding from a `parameters_schema` key to an argv position.

    `name` NAMES a schema key (cross-checked at the slice). Exactly one
    of `flag` / `position` is set (flag mode vs positional mode).
    `required=True` means the conduct fails if the Run's
    effective_parameters lack the key.
    """

    name: str
    flag: str | None = None
    position: int | None = None
    required: bool = False
    style: ArgStyle = ArgStyle.VALUE


@dataclass(frozen=True)
class LaunchSpec:
    """A Method's full launch recipe: literal base command + ordered bindings.

    `base_command` is the literal argv prefix. `args` are order-
    significant bindings (flag-mode args render in declared order;
    positional-mode args render by `position`). `input_arg` / `output_arg`
    are the flags preceding the caller-supplied input / output URIs
    (None => append the URI positionally).
    """

    base_command: tuple[str, ...]
    args: tuple[LaunchArg, ...] = ()
    input_arg: str | None = None
    output_arg: str | None = None


def validate_launch_spec(spec: LaunchSpec) -> None:
    """Raise `InvalidLaunchSpecError` if `spec` is not well-formed.

    Self-contained checks only (no schema). See module docstring for the
    well-formedness-vs-cross-check split.
    """
    if not spec.base_command:
        raise InvalidLaunchSpecError("base_command must have at least one token")
    if any(not token for token in spec.base_command):
        raise InvalidLaunchSpecError("base_command tokens must be non-empty")

    seen_names: set[str] = set()
    positions: list[int] = []
    for arg in spec.args:
        if not arg.name:
            raise InvalidLaunchSpecError("a LaunchArg.name must be non-empty")
        if arg.name in seen_names:
            raise InvalidLaunchSpecError(f"duplicate LaunchArg name {arg.name!r}")
        seen_names.add(arg.name)

        has_flag = arg.flag is not None
        has_position = arg.position is not None
        if has_flag == has_position:
            raise InvalidLaunchSpecError(
                f"LaunchArg {arg.name!r} must set exactly one of flag / position"
            )
        if has_flag and not _FLAG_RE.match(arg.flag or ""):
            raise InvalidLaunchSpecError(
                f"LaunchArg {arg.name!r} flag {arg.flag!r} is not a valid option"
            )
        if arg.style is ArgStyle.FLAG_ONLY and not has_flag:
            raise InvalidLaunchSpecError(
                f"LaunchArg {arg.name!r} style flag_only requires a flag, not a position"
            )
        if has_position:
            if (arg.position or 0) < 0:
                raise InvalidLaunchSpecError(f"LaunchArg {arg.name!r} position must be >= 0")
            positions.append(arg.position or 0)

    # Positional args must be a contiguous 0..n-1 block (no gaps / dups)
    # so argv assembly order is unambiguous.
    if sorted(positions) != list(range(len(positions))):
        raise InvalidLaunchSpecError("positional args must occupy contiguous positions 0..n-1")

    for label, flag in (("input_arg", spec.input_arg), ("output_arg", spec.output_arg)):
        if flag is not None and not _FLAG_RE.match(flag):
            raise InvalidLaunchSpecError(f"{label} {flag!r} is not a valid option")


def launch_spec_to_dict(spec: LaunchSpec) -> dict[str, Any]:
    """JSON-friendly, ORDER-PRESERVING serialization.

    `args` are NOT sorted: their order is semantic (it is argv order).
    Used both for the event payload and for `Method.content_subset`, so
    two recipes differing only in argv order hash differently.
    """
    return {
        "base_command": list(spec.base_command),
        "args": [
            {
                "name": arg.name,
                "flag": arg.flag,
                "position": arg.position,
                "required": arg.required,
                "style": arg.style.value,
            }
            for arg in spec.args
        ],
        "input_arg": spec.input_arg,
        "output_arg": spec.output_arg,
    }


def launch_spec_from_dict(data: dict[str, Any]) -> LaunchSpec:
    """Rebuild a `LaunchSpec` from its `launch_spec_to_dict` form.

    `Any`-typed like the aggregate `from_stored` codecs: jsonb payloads
    arrive untyped and are reconstructed by position/key here.
    """
    raw_args: list[dict[str, Any]] = data.get("args", [])
    args = tuple(
        LaunchArg(
            name=a["name"],
            flag=a.get("flag"),
            position=a.get("position"),
            required=a.get("required", False),
            style=ArgStyle(a.get("style", ArgStyle.VALUE.value)),
        )
        for a in raw_args
    )
    return LaunchSpec(
        base_command=tuple(data["base_command"]),
        args=args,
        input_arg=data.get("input_arg"),
        output_arg=data.get("output_arg"),
    )


__all__ = [
    "ArgStyle",
    "InvalidLaunchSpecError",
    "LaunchArg",
    "LaunchSpec",
    "launch_spec_from_dict",
    "launch_spec_to_dict",
    "validate_launch_spec",
]
