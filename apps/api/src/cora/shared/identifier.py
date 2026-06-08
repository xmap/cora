"""Shared identifier value objects.

This module owns three families of identifier value object used across
multiple bounded contexts:

  - `Identifier(scheme, value)`: open-scheme anti-corruption-ref pair for
    upstream-deferred concepts CORA does NOT model as first-class
    aggregates (proposal, btr, lab visit, session, cycle, and so on).
  - `PersistentIdentifier(scheme, value)`: PIDINST v1.0 Property 1 tuple
    with a closed-enum scheme `{DOI, HANDLE}`, the persistent identifier
    of an instrument (or facility) under PIDINST.
  - `AlternateIdentifier(kind, value)`: PIDINST v1.0 Property 13 tuple
    with a closed-enum kind `{SerialNumber, InventoryNumber, Other}`,
    the instance-tier alternate identifier distinct from the PID-tier.

PID-tier and 3-tuple shapes stay bespoke (separate dataclasses; they do
NOT compose `Identifier`) per PIDINST's distinct semantic layers. 3-tuple
VOs (`Manufacturer`, `AssetOwner`, `Drawing`, `ScopeRef`, `ModelRef`) each
carry a load-bearing third field and stay at their carrier aggregates.

Closed-vocabulary discipline lives on the CARRIER aggregate; the open
`Identifier` VO keeps the scheme free-form. Per-aggregate closed-enum
types MUST enforce their closed-enum invariant at their OWN `__post_init__`
BEFORE delegating to any shared validator; the `Identifier` VO never sees
the closed-enum context.

`PersistentIdentifier` and `AlternateIdentifier` were originally bespoke
at `cora.equipment.aggregates.asset.state` (Asset was the first consumer).
The Session 5 Slice 5 Facility aggregate is the rule-of-three trigger that
hoisted them here; Federation BC cannot import from Equipment per the tach
config, and these VOs are genuinely shared PIDINST primitives rather than
Equipment-domain types.

Carrier-bound errors (e.g. `AssetPersistentIdAlreadyAssignedError`,
`AssetAlternateIdentifierAlreadyPresentError`) stay at their carrier
aggregates; only the VOs + VO-construction errors + the from_stored wrap
error are hoisted.

Cross-reference [[project-identifier-vo-design]] for the locked shape, the
pre-pilot wire-key rename (`id -> value`), the deviation allowlist, and the
federation-readiness notes. Cross-reference [[project-facility-aggregate-design]]
for the Sub-Slice 0 hoist rationale.
"""

from dataclasses import dataclass
from enum import StrEnum

from cora.shared.bounded_text import validate_bounded_text

IDENTIFIER_SCHEME_MAX_LENGTH = 50
IDENTIFIER_VALUE_MAX_LENGTH = 200
ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH = 200
PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH = 200


class InvalidIdentifierError(ValueError):
    """An Identifier's scheme or value is empty, whitespace-only, or too long.

    The `value` attribute carries the ORIGINAL untrimmed input so callers
    can diagnose whitespace-only rejections without losing the offending
    characters.
    """

    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"Identifier {field} is invalid (got: {value!r})")
        self.field = field
        self.value = value


@dataclass(frozen=True, slots=True)
class Identifier:
    """Open-scheme identifier pair. Free-form scheme; per-site closed-enum
    discipline lives at the carrier aggregate, not on this VO."""

    scheme: str
    value: str

    def __post_init__(self) -> None:
        scheme_trimmed = self.scheme.strip()
        if not scheme_trimmed or len(scheme_trimmed) > IDENTIFIER_SCHEME_MAX_LENGTH:
            raise InvalidIdentifierError(field="scheme", value=self.scheme)
        value_trimmed = self.value.strip()
        if not value_trimmed or len(value_trimmed) > IDENTIFIER_VALUE_MAX_LENGTH:
            raise InvalidIdentifierError(field="value", value=self.value)
        object.__setattr__(self, "scheme", scheme_trimmed)
        object.__setattr__(self, "value", value_trimmed)


class AlternateIdentifierKind(StrEnum):
    """Closed vocabulary for an alternate-identifier kind.

    Values are verbatim from PIDINST v1.0 spec page 8 (Table 1)
    Property 13 `alternateIdentifierType` controlled vocabulary:
    SerialNumber, InventoryNumber, Other. Operationally:

      - `SerialNumber` is the manufacturer's per-unit identifier
        (the value engraved on the chassis or printed on the QR
        sticker; for example, an Aerotech ANT130-L's `12345-ABC`).
      - `InventoryNumber` is the facility-issued asset tag (for
        example, an APS-issued `APS-2BM-CAM-001`).
      - `Other` is the catch-all for vendor-specific or
        unconventional identifier schemes that don't fit the prior
        two; resolution is operator-supplied free text in the
        `value` field.

    Adding a fourth member is an additive enum change at a future
    migration boundary. The closed-enum stance mirrors
    `ManufacturerIdentifierType` (Model BC) and the broader
    [[project-family-affordance-design]] closed-vocabulary
    precedent. See [[project-asset-alternate-identifiers-design]]
    Lock B for the design rationale.
    """

    SERIAL_NUMBER = "SerialNumber"
    INVENTORY_NUMBER = "InventoryNumber"
    OTHER = "Other"


class InvalidAlternateIdentifierValueError(ValueError):
    """The supplied alternate-identifier value is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Alternate identifier value must be 1-{ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class AlternateIdentifier:
    """A flat (kind, value) tuple identifying an entity under an alternate scheme.

    Deviation from Identifier VO: pre-committed to gain PIDINST 13.2
    alternateIdentifierName as a third field.

    PIDINST v1.0 Property 13: instance-tier alternate identifiers
    distinct from the PID-tier persistent identifier. Examples:

      - `(SerialNumber, "12345-ABC")` for a manufacturer's serial
      - `(InventoryNumber, "APS-2BM-CAM-001")` for a facility asset tag
      - `(Other, "RIC-99")` for a legacy or vendor-specific scheme

    `value` is trimmed and length-bounded 1-200 chars via the shared
    `validate_bounded_text` helper, matching the
    `ManufacturerIdentifier` precedent in the Model BC. The VO is
    FLAT (kind + value); no scheme URIs, namespaces, or labels per
    [[project-asset-alternate-identifiers-design]] Lock C. Pairing
    uniqueness across carriers is NOT enforced by the VO; carrier
    aggregates own their own uniqueness rules.
    """

    kind: AlternateIdentifierKind
    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
            error_class=InvalidAlternateIdentifierValueError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


class PersistentIdentifierScheme(StrEnum):
    """Closed PIDINST v1.0 Property 1 identifier-type vocabulary (subset).

    Values match `PidinstIdentifierType.DOI.value` and
    `PidinstIdentifierType.HANDLE.value` byte-for-byte so the
    serializer swap (URN to DOI / Handle) does not need a translation
    map. URN and URL members of `PidinstIdentifierType` are
    intentionally NOT mirrored here: a persistent identifier is an
    assigned-by-operator persistent identifier, not a runtime fallback
    or a content URL.

    Adding a fourth member (for example ARK or PURL) is an additive
    enum change at a future migration boundary, gated on operator
    demand. The closed-enum stance mirrors `AlternateIdentifierKind`
    and `ManufacturerIdentifierType`.
    """

    DOI = "DOI"
    HANDLE = "Handle"


class InvalidPersistentIdentifierValueError(ValueError):
    """The supplied persistent_id value is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Persistent identifier value must be "
            f"1-{PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class PersistentIdentifier:
    """PIDINST v1.0 Property 1: the persistent identifier of an instrument.

    Deviation from Identifier VO: closed-enum scheme {DOI, HANDLE} +
    PIDINST property 1 single-primary semantic.

    Tuple `(scheme, value)` where `scheme` is a closed
    `PersistentIdentifierScheme` member and `value` is the operator-
    supplied opaque string identifying the entity under that scheme.

    Examples:
      - `(DOI, "10.5281/zenodo.1234567")` for a Zenodo-minted DOI
      - `(DOI, "10.13139/OLCF/1234")` for an OLCF-minted DOI
      - `(HANDLE, "20.500.12613/12345")` for a Handle.net record

    `value` is trimmed and length-bounded 1-200 chars via the shared
    `validate_bounded_text` helper, matching the
    `AlternateIdentifier.value` precedent. The VO is FLAT (scheme +
    value); no resolver URLs, no prefix / suffix split. Pairing
    enforcement is implicit: scheme is a non-None enum member by
    construction, value is non-empty by `validate_bounded_text`.

    Set-once invariant lives at the carrier aggregate level (the
    decider), not on the VO: a `PersistentIdentifier` instance is
    always valid standalone; the carrier's state enforces that only
    one ever lands.
    """

    scheme: PersistentIdentifierScheme
    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH,
            error_class=InvalidPersistentIdentifierValueError,
        )
        object.__setattr__(self, "value", trimmed)


class MalformedPersistentIdentifierError(Exception):
    """A stored persistent-identifier-assigned payload failed deserialization.

    Wraps any underlying `ValueError` raised by
    `PersistentIdentifierScheme(...)` or `PersistentIdentifier(...)` at
    `from_stored` time, per the [[project-from-stored-wrap-convention]]
    precedent (mirrors `Malformed*` siblings in other BCs). The
    evolver itself never raises; it trusts that `from_stored` already
    wrapped any malformed payload as this error class.
    """


__all__ = [
    "ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH",
    "IDENTIFIER_SCHEME_MAX_LENGTH",
    "IDENTIFIER_VALUE_MAX_LENGTH",
    "PERSISTENT_IDENTIFIER_VALUE_MAX_LENGTH",
    "AlternateIdentifier",
    "AlternateIdentifierKind",
    "Identifier",
    "InvalidAlternateIdentifierValueError",
    "InvalidIdentifierError",
    "InvalidPersistentIdentifierValueError",
    "MalformedPersistentIdentifierError",
    "PersistentIdentifier",
    "PersistentIdentifierScheme",
]
