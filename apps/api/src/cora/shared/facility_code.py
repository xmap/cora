"""`FacilityCode` value object: cross-deployment convergent facility slug.

The cross-deployment convergent identity for a facility per the locked
two-tier identity design (`Facility.id: UUID` internal-opaque PK +
`Facility.code: FacilityCode` cross-deployment slug). Appears at every
port surface that names a facility for cross-BC and cross-deployment
purposes: `CredentialLookupResult.facility_id`, `PermitLookupResult.
peer_facility_id`, the `PermitLookup.lookup_outbound / lookup_inbound`
keys, and the Calibration BC `publish_revision` call sites.

Wire payloads (event payloads, command DTOs) keep bare `str` on disk;
the VO is in-memory only at the port surface. Handlers construct
`FacilityCode(command.peer_facility_id)` at the port edge and pass the
typed VO to the port; the projection-row adapter constructs the VO from
the raw `TEXT` column.

## Shape

`@dataclass(frozen=True, slots=True)` with a single `value: str` field
(matches the `bounded_name` shape). Validation runs in `__post_init__`
because the codepoint set is regex-bounded (lowercase ASCII alphanumeric
+ dash, 1-32 chars), which the `bounded_name` decorator does not express.

## Validation

  - `value` is trimmed (leading/trailing whitespace stripped before length
    + regex checks); the trimmed value is what gets installed on the
    instance.
  - Trimmed length MUST be 1-32 chars.
  - Trimmed value MUST match `^[a-z0-9-]{1,32}$` (lowercase ASCII letters,
    digits, dash). No uppercase, no underscore, no slash, no dot.

The regex is deliberately strict: cross-deployment convergent identity
means two facilities that both call themselves "aps" must produce equal
`FacilityCode` values byte-for-byte across the wire. Allowing mixed
case ("APS" vs "aps") would silently fork identity.

## Error class

`InvalidFacilityCodeError(value)` carries the ORIGINAL untrimmed input
so callers can diagnose whitespace-only or wrong-case rejections without
losing the offending characters (mirrors the `bounded_name` /
`Identifier` precedent).

## Why not `bounded_name` decorator

The `bounded_name` decorator handles trim + length + empty-after-trim
rejection but does NOT express regex codepoint restrictions. Adding a
`pattern` knob to the decorator is a rule-of-three call; with only one
codepoint-restricted VO today (this one), a bespoke `__post_init__`
keeps the shared decorator surface minimal. Re-evaluate when a SECOND
codepoint-restricted VO lands.

Cross-reference [[project-structural-scope-design]] for the locked
two-tier identity design and the per-site migration plan.
"""

import re
from dataclasses import dataclass

FACILITY_CODE_MAX_LENGTH = 32
"""Max length (inclusive) for `FacilityCode.value` after trim.

32 chars matches the convergent-slug budget across known facility
identifier conventions (e.g. ROR-style 9-char short codes, ISA-95
Site identifiers, common synchrotron short names like `maxiv`, `esrf`,
`spring8`). Re-visit if a real facility code exceeds 32 chars.
"""

_FACILITY_CODE_PATTERN = re.compile(r"^[a-z0-9-]{1,32}$")
"""Pre-compiled codepoint pattern: lowercase ASCII alphanumeric + dash,
1-32 chars. The pattern is locked at module load so every construction
runs against the same compiled regex."""


class InvalidFacilityCodeError(ValueError):
    """A `FacilityCode`'s value is empty, whitespace-only, too long, or
    contains disallowed codepoints (anything outside `[a-z0-9-]`).

    The `value` attribute carries the ORIGINAL untrimmed input so callers
    can diagnose whitespace-only or wrong-case rejections without losing
    the offending characters.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"FacilityCode must be 1-{FACILITY_CODE_MAX_LENGTH} lowercase ASCII "
            f"alphanumeric or dash chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True, slots=True)
class FacilityCode:
    """Cross-deployment convergent facility slug.

    Single `value: str` field, trimmed and pattern-validated in
    `__post_init__`. Two `FacilityCode` instances with the same trimmed
    value compare equal and hash equal; substitutable everywhere a port
    surface names a facility for cross-BC or cross-deployment purposes.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not _FACILITY_CODE_PATTERN.fullmatch(trimmed):
            raise InvalidFacilityCodeError(self.value)
        object.__setattr__(self, "value", trimmed)

    def __str__(self) -> str:
        return self.value


__all__ = [
    "FACILITY_CODE_MAX_LENGTH",
    "FacilityCode",
    "InvalidFacilityCodeError",
]
