"""SignalType NewType for Role.produces / Role.consumes vocabulary.

`Role.produces` and `Role.consumes` declare which signal-flow vocabulary
items a satisfying Asset emits or accepts. The vocabulary is currently
operator-supplied free text (matching `AssetPort.signal_type`'s shipped
50-char free-text convention); the NewType wrapper makes the contract
type-distinct so future tooling can grep for SignalType-bearing fields
without false-matching on every bare `str`.

## Vocabulary status

Open-vocabulary at this slice (no closed StrEnum). Operators stamp
short labels ("EncoderPosition", "TriggerOut", "Image",
"Frame", "ReferenceClock") at Role definition time. A closed enum may
land later if a rule-of-three name collision motivates it; today the
free-text convention matches `AssetPort.signal_type`'s precedent and
keeps the cross-aggregate equality check straightforward (a Role's
`produces` matches an `AssetPort` with `direction='out'` iff the
strings compare equal after trimming).

## Validation

Length + trimming happens at decider time, mirroring
`AssetPort.signal_type`'s `PORT_SIGNAL_TYPE_MAX_LENGTH = 50` bound
and trim-then-validate flow. The NewType wrapper does NOT validate at
runtime (NewType is zero-cost); callers MUST pass an
already-normalized string.

## Why a NewType, not a bounded_name VO

Free-text VOs (`FamilyName`, `RoleName`, `AssetName`) carry a single
value field and a constructor that trims + bounds. SignalType is a
set-member label, not a name with display semantics: collections of
SignalType strings are the unit of comparison (Role.produces is a
frozenset, AssetPort emits one), so a bare wrapped string serializes
to JSON / postgres natively and supports `frozenset` membership tests
without unwrapping. A bounded_name VO would force every comparison
through a `.value` accessor with no compensating type-safety gain.
"""

from typing import NewType

SIGNAL_TYPE_MAX_LENGTH = 50

SignalType = NewType("SignalType", str)


class InvalidSignalTypeError(ValueError):
    """The supplied SignalType value is empty, whitespace-only, or too long."""

    def __init__(self, value: object) -> None:
        super().__init__(
            f"SignalType must be 1-{SIGNAL_TYPE_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


def normalize_signal_type(value: str) -> SignalType:
    """Trim, bound-check, and wrap a raw string as a `SignalType`.

    Raises `InvalidSignalTypeError` on empty / whitespace-only / too-long
    input. Intended for decider-time normalization at the point a Role
    is defined.
    """
    trimmed = value.strip()
    if not trimmed or len(trimmed) > SIGNAL_TYPE_MAX_LENGTH:
        raise InvalidSignalTypeError(value)
    return SignalType(trimmed)


__all__ = [
    "SIGNAL_TYPE_MAX_LENGTH",
    "InvalidSignalTypeError",
    "SignalType",
    "normalize_signal_type",
]
