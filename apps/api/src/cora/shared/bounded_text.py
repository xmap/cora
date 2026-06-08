"""Trimmed-bounded-text validation helper for value object `__post_init__`.

Originally hoisted as `validate_name` after the 10th bounded-name VO
landed (`PlanName`). Renamed to `validate_bounded_text` once the
helper picked up non-name callers (Run / Subject / Dataset reason
VOs + Decision choice/context/rule VOs) — the
shared concept across all sites is "trimmed string with a bounded
length", not "name".

Why hoist a function (not a class)
-----------------------------------
The duplicated body across the call sites was, originally, the
**trim + length-check + raise** logic, not the dataclass shape itself.
Hoisting only the validation function preserved what's worth keeping
per-VO:

  - Distinct frozen dataclass type (`isinstance` checks stay
    aggregate-specific; pyright keeps `ActorName` and `MethodName`
    apart at type sites).
  - Distinct error class with aggregate-specific message text.
  - Per-VO `MAX_LENGTH` constant in the aggregate's state module
    (read by both the VO and the API-boundary Pydantic schema).

A `BoundedText` base class would couple all aggregates to one type
and make per-VO documentation harder to navigate. A class factory
would weaken `isinstance` semantics. A free function avoids both.

Why also hoist a decorator (not just the function)
--------------------------------------------------
Once the function-helper count crossed the rule-of-three trigger for
homogeneous `value: str`-only *Name VOs, the duplicated body at the
call site stopped being just the validation call: it became the
three-line `__post_init__` ritual (call helper, `object.__setattr__`
the trimmed value, blank line). The decorator `bounded_name` removes
that ritual at every site while preserving everything the function
hoist already preserved (distinct type, distinct error class,
aggregate-local MAX_LENGTH constant, isinstance distinction).

See `project_axes_foundation.md` for the underlying "thread the
needle: shared mechanism without shared identity" axis. The function
stays exported and continues to back the decorator internally; it
also remains the right tool for the non-decorator-eligible call sites
which fall into three buckets:

  1. Composite multi-field VOs that validate per-field within one
     `__post_init__` (e.g. `AssetPort`, `Drawing`, `AssetOwner`,
     `AlternateIdentifier`).
  2. Bare-string validation embedded in deciders (e.g. reason text
     validation in `stop_run` / `truncate_run` / `abort_run` /
     `adjust_run` / `expire_clearance` / `reject_clearance` and the
     various `register_*` slices).
  3. VOs with non-standard rejection semantics (e.g.
     `CalibrationDescription` accepts empty-after-trim and rejects
     only on over-length, which `validate_bounded_text` does NOT
     express).

Current `MAX_LENGTH` values across the codebase: {50, 100, 200, 255,
2000}. The 2000-char value (`CautionText`) is single-field but its
naming-of-symbol semantics differ from the *Name VOs; whether it
adopts the decorator is a per-VO call at refactor time.

How VOs use the decorator
-------------------------
The decorator goes ABOVE `@dataclass(frozen=True)` at the call site.
Decorators apply bottom-up: `@dataclass` runs first and synthesizes
`__init__`, then `@bounded_name` wraps that synthesized `__init__`
to trim + length-check the incoming value before storing it.

    @bounded_name(max_length=ACTOR_NAME_MAX_LENGTH, error_class=InvalidActorNameError)
    @dataclass(frozen=True)
    class ActorName:
        value: str

The error class's constructor is called with the **original**
(untrimmed) value so its message can quote what the caller actually
sent.

Why wrap `__init__` (and not install `__post_init__`)
-----------------------------------------------------
`dataclasses._process_class` decides at DECORATION time whether to
emit a `self.__post_init__()` call site in the synthesized `__init__`,
based on `hasattr(cls, '__post_init__')` at that moment. Installing
`__post_init__` later via `setattr` is a silent no-op for classes
that did not define one before `@dataclass` ran. Wrapping `__init__`
instead is always sound: the synthesized `__init__` is always present
after `@dataclass(frozen=True)` and is always called at construction.
A user-authored `__post_init__` (rare but supported) still chains
correctly because the synthesized `__init__` calls it AFTER the
wrapped original `__init__` has stored the trimmed value.

Pyright invariants preserved (strict mode)
------------------------------------------
With `Callable[[type[T]], type[T]]` as the decorator's return type:

  - `PolicyName` is `type[PolicyName]` at every reference site.
  - `PolicyName('x')` is `PolicyName`.
  - `.value` is `str`.
  - isinstance narrowing inside `if isinstance(x, PolicyName):` works.
  - `__match_args__` lets `case PolicyName(value=v):` match.
  - Frozen `p.value = 'mut'` is flagged with
    `reportAttributeAccessIssue`.
  - `PolicyName()` flagged with `reportCallIssue` (missing argument).
  - `PolicyName('a', 'b')` flagged with `reportCallIssue`
    (extra argument).

The trim transformation itself is not visible to pyright; that's a
runtime invariant the per-VO test files pin.

Decoration-time guards
----------------------
`bounded_name` raises `TypeError` at class-decoration time when:

  - The class is not a dataclass (typically: `@dataclass` was placed
    BELOW `@bounded_name` by mistake, so the wrapped class isn't
    yet a dataclass when `bounded_name` sees it).
  - The class lacks a `value` field.

Both errors fire at module import; neither can ship a silently-broken
VO into production.
"""

from collections.abc import Callable
from dataclasses import is_dataclass
from typing import TypeVar

T = TypeVar("T")


def validate_bounded_text(
    value: str,
    *,
    max_length: int,
    error_class: type[Exception],
) -> str:
    """Trim, length-check, return the trimmed value, or raise `error_class`.

    Raises `error_class(value)` (the original untrimmed value) if the
    trimmed result is empty or exceeds `max_length`. Otherwise returns
    the trimmed string for the VO to install on itself.
    """
    trimmed = value.strip()
    if not trimmed or len(trimmed) > max_length:
        raise error_class(value)
    return trimmed


def bounded_name(
    *,
    max_length: int,
    error_class: type[Exception],
) -> Callable[[type[T]], type[T]]:
    """Wrap a frozen-dataclass `value: str` VO with trim + length-check.

    Apply ABOVE `@dataclass(frozen=True)`:

        @bounded_name(max_length=POLICY_NAME_MAX_LENGTH, error_class=InvalidPolicyNameError)
        @dataclass(frozen=True)
        class PolicyName:
            value: str

    The decorator wraps the dataclass-synthesized `__init__` so that
    every construction of `PolicyName(...)` trims the input, raises
    `error_class(value)` with the ORIGINAL untrimmed value on empty
    or over-length, and stores the trimmed value via the synthesized
    `__init__`'s normal `object.__setattr__('value', ...)` call site.
    The class object is returned in place (no subclass, no factory),
    so `isinstance`, `__match_args__`, `__eq__`, `__hash__`, and
    `__repr__` are all preserved.

    Raises `TypeError` at decoration time if the decorated class is
    not a dataclass (`@dataclass` belongs ABOVE `@bounded_name` so
    that `@dataclass` runs first and `@bounded_name` sees a real
    dataclass) or if the class lacks a `value` field.
    """

    def decorate(cls: type[T]) -> type[T]:
        if not is_dataclass(cls):
            raise TypeError(
                f"@bounded_name must be applied above @dataclass on {cls.__name__}; "
                f"saw a non-dataclass class. Decorator order: "
                f"@bounded_name OUTER, @dataclass(frozen=True) INNER."
            )
        if "value" not in cls.__dataclass_fields__:  # pyright: ignore[reportAttributeAccessIssue]
            raise TypeError(f"@bounded_name requires a `value` field on {cls.__name__}")

        original_init = cls.__init__

        def wrapped_init(self: T, value: str) -> None:
            trimmed = validate_bounded_text(value, max_length=max_length, error_class=error_class)
            original_init(self, trimmed)  # pyright: ignore[reportCallIssue]

        cls.__init__ = wrapped_init  # pyright: ignore[reportAttributeAccessIssue]
        return cls

    return decorate


__all__ = ["bounded_name", "validate_bounded_text"]
