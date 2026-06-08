"""Hazard classification: discriminated-union value object kernel for the Safety BC.

Lives in the BC root (importable from any feature) per the cross-BC
shared-kernel pattern (mirrors `cora.shared.json_schema_validation`
for schema-validated values, and `cora.shared.bounded_text` for
trimmed-bounded names).

Per [[project_safety_clearance_design]] §"HazardClassification discriminated
union VO", the kernel is a four-arm discriminated union:

  - `NFPA704Rating(health, flammability, instability, special?)` -- the
    universally-posted "fire diamond" 0-4 rating + special enum. Operator-
    recognizable on every chemical label at facility lab spaces.
  - `RiskBand{Green, Yellow, Red}` -- synchrotron-convergent triage banding
    used by 6 of 8 surveyed facilities (NSLS-II, ESRF, MAX IV, DLS, DESY,
    ALS variants). Maps to HSE ALARP three-band semantics (Broadly
    Acceptable / Tolerable / Unacceptable).
  - `GHSPictogram(code, statement_codes)` -- GHS pictogram code (GHS01..GHS09)
    + the H-codes (hazard statements) that triggered the pictogram. The
    global SDS-aligned chemical-classification scheme.
  - `SchemeCode(scheme, code, severity_label)` -- generic fallback for the
    schemes that don't fit the three typed arms (ANSI Z136 laser classes,
    BSL biosafety levels, IAEA radiation categories, APS Experiment Hazard
    Classes, NFPA 704 alternates, etc.).

Severity is multi-dimensional and scheme-dependent per the literature
(IEC 61508 SIL is one axis, GHS Categories are another, BSL another).
NEVER normalize severity across schemes. The discriminated-union shape
preserves each scheme's native severity vocabulary verbatim.

## Why a discriminated union (not a flat `(scheme, code)` tuple)

The v2 research pass surfaced NFPA 704 as a strong VO precedent: every
chemical label at APS-like facility lab spaces shows the 4-quadrant 0-4
diamond. Encoding it as `SchemeCode(scheme="NFPA_704", code="2-3-1-OX")`
loses the structure (you can't compare or query individual quadrants
without re-parsing the code string). A typed `NFPA704Rating` makes the
quadrants first-class.

Same argument for `RiskBand`: 6 of 8 surveyed facility safety forms
(NSLS-II SAF, ESRF A-form/SAF, MAX IV DUO+ESRA, DLS ERA+PLHD, DESY DOOR,
ALS ESAF variants) use Green/Yellow/Red triage. Lifting it as a typed
StrEnum makes the operator-recognizable concept first-class without
forcing a separate Risk aggregate (the four-primitive split's bottom
half is deferred per `[gap]` watch item #1 in
[[project_safety_clearance_design]]).

GHS likewise: H-statements (H300, H311, etc.) and pictograms (GHS01..09)
are the ISO standard for chemical hazard communication; modeling them as
opaque (scheme, code) loses the typed structure.

The generic `SchemeCode` arm absorbs everything else (ANSI Z136, BSL,
IAEA, APS Experiment Hazard Class) where the scheme-specific structure
isn't worth a typed VO until it earns one (rule of three).

## Future evolution

When a new scheme proves it warrants a typed VO (next likely candidate:
ANSI Z136 laser classes if the laser-using pilots multiply), promote it
from `SchemeCode` to its own typed arm. Backward-compat: existing
`SchemeCode(scheme="ANSI_Z136", code="Class_4", ...)` rows survive as-is;
the new typed arm is opt-in for new declarations.

When the four-primitive split's RiskAssessment + Barrier aggregates land
([gap] watch item #1), `HazardClassification` stays as the intrinsic
descriptor; RiskAssessment carries the situational `severity x likelihood`
calculation that references one or more HazardClassifications. The kernel
shape doesn't change.
"""

from dataclasses import dataclass, field
from enum import StrEnum

# ---------------------------------------------------------------------------
# Bounds + validation constants (shared across the union arms)
# ---------------------------------------------------------------------------

NFPA704_MIN_RATING = 0
NFPA704_MAX_RATING = 4
NFPA704_VALID_SPECIAL = frozenset(
    {"OX", "W", "SA", "COR", "ACID", "ALK", "BIO", "POI", "RA", "CRYO"}
)

GHS_PICTOGRAM_MIN_CODE = "GHS01"
GHS_PICTOGRAM_MAX_CODE = "GHS09"
GHS_VALID_PICTOGRAMS = frozenset(
    {"GHS01", "GHS02", "GHS03", "GHS04", "GHS05", "GHS06", "GHS07", "GHS08", "GHS09"}
)
GHS_STATEMENT_CODE_MAX_LENGTH = 16

SCHEME_CODE_SCHEME_MAX_LENGTH = 50
SCHEME_CODE_CODE_MAX_LENGTH = 100
SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH = 100


# ---------------------------------------------------------------------------
# Errors (raised at __post_init__ on construction; trim/length enforced)
# ---------------------------------------------------------------------------


class InvalidNFPA704RatingError(ValueError):
    """An NFPA 704 quadrant rating was out of bounds (must be 0-4 int)."""

    def __init__(self, axis: str, value: object) -> None:
        super().__init__(f"NFPA 704 {axis} rating must be int in [0, 4] (got: {value!r})")
        self.axis = axis
        self.value = value


class InvalidNFPA704SpecialError(ValueError):
    """The NFPA 704 'special' field carries an unrecognized code."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"NFPA 704 'special' must be one of "
            f"{sorted(NFPA704_VALID_SPECIAL)} or None (got: {value!r})"
        )
        self.value = value


class InvalidGHSPictogramCodeError(ValueError):
    """The GHS pictogram code is not in the closed enum GHS01..GHS09."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"GHS pictogram code must be one of {sorted(GHS_VALID_PICTOGRAMS)} (got: {value!r})"
        )
        self.value = value


class InvalidGHSStatementCodeError(ValueError):
    """A GHS H-statement code is empty or exceeds the length cap."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"GHS statement code must be 1-{GHS_STATEMENT_CODE_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidSchemeCodeError(ValueError):
    """Generic SchemeCode field is empty, whitespace-only, or too long."""

    def __init__(self, field_name: str, value: str, max_length: int) -> None:
        super().__init__(
            f"SchemeCode {field_name} must be 1-{max_length} chars after trimming (got: {value!r})"
        )
        self.field_name = field_name
        self.value = value
        self.max_length = max_length


# ---------------------------------------------------------------------------
# RiskBand: synchrotron-convergent traffic-light triage; HSE ALARP-aligned
# ---------------------------------------------------------------------------


class RiskBand(StrEnum):
    """Three-band risk triage; mirrors HSE ALARP semantics.

    6 of 8 surveyed facility safety forms use Green/Yellow/Red triage:
      - `Green`  -- broadly acceptable; baseline operating posture
      - `Yellow` -- tolerable with controls; safety review required
      - `Red`    -- requires authorization-by-licensing; restricted

    Per the Safety design memo, this lives ON Clearance as an optional
    field (`risk_band: RiskBand | None`). APS ESAF doesn't use bands;
    the field is None for ESAF Clearances and populated for ESRF / MAX
    IV / DLS / DESY / SLAC variants. Future Risk aggregate (when the
    four-primitive split's bottom half lands) carries the calculated
    band; today the band is captured at submit time as audit data.
    """

    GREEN = "Green"
    YELLOW = "Yellow"
    RED = "Red"


# ---------------------------------------------------------------------------
# NFPA 704: the "fire diamond" 0-4 four-quadrant rating
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NFPA704Rating:
    """NFPA 704 'fire diamond' rating: health / flammability / instability / special.

    The universally-posted chemical-label rating at APS-like facility
    lab spaces. Each quadrant is a 0-4 int; the optional 'special'
    quadrant carries a short alpha code (OX = oxidizer, W = water-
    reactive, SA = simple asphyxiant, etc.).

    Validated at construction; raises `InvalidNFPA704RatingError` for
    out-of-range quadrants and `InvalidNFPA704SpecialError` for
    unrecognized special codes.
    """

    health: int
    flammability: int
    instability: int
    special: str | None = None

    def __post_init__(self) -> None:
        # Defensive: bool is a subclass of int in Python; reject explicitly so
        # `NFPA704Rating(health=True, ...)` doesn't silently coerce to 1.
        for axis, value in (
            ("health", self.health),
            ("flammability", self.flammability),
            ("instability", self.instability),
        ):
            if isinstance(value, bool) or not isinstance(value, int):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise InvalidNFPA704RatingError(axis, value)
            if value < NFPA704_MIN_RATING or value > NFPA704_MAX_RATING:
                raise InvalidNFPA704RatingError(axis, value)
        if self.special is not None and self.special not in NFPA704_VALID_SPECIAL:
            raise InvalidNFPA704SpecialError(self.special)


# ---------------------------------------------------------------------------
# GHS: pictogram + triggering H-statements
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GHSPictogram:
    """GHS chemical hazard pictogram + triggering H-statement codes.

    GHS pictogram codes are GHS01..GHS09 (closed enum). `statement_codes`
    is the frozenset of H-codes (for example, 'H300', 'H311') whose presence on
    the chemical's SDS triggered the pictogram. Empty `statement_codes`
    is allowed (a pictogram declared without specific H-code attribution).

    Validated at construction; raises `InvalidGHSPictogramCodeError` for
    unrecognized pictogram codes and `InvalidGHSStatementCodeError` for
    empty/oversized H-codes.
    """

    code: str
    statement_codes: frozenset[str] = field(default_factory=frozenset[str])

    def __post_init__(self) -> None:
        if self.code not in GHS_VALID_PICTOGRAMS:
            raise InvalidGHSPictogramCodeError(self.code)
        for stmt in self.statement_codes:
            trimmed = stmt.strip()
            if not trimmed or len(trimmed) > GHS_STATEMENT_CODE_MAX_LENGTH:
                raise InvalidGHSStatementCodeError(stmt)


# ---------------------------------------------------------------------------
# SchemeCode: generic fallback for non-typed schemes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemeCode:
    """Generic (scheme, code, severity_label) triple for non-typed schemes.

    Catches everything that doesn't (yet) warrant a typed VO arm:
    ANSI Z136 laser classes (Class 1/1M/2/2M/3R/3B/4), BSL biosafety
    levels (BSL-1..4), IAEA radiation categories, APS Experiment Hazard
    Classes (7.1, 8.1, 14.1, etc.).

    `severity_label` is the scheme's native severity descriptor
    (verbatim, never normalized). Empty severity is allowed (some schemes
    encode severity in the code itself).

    All three fields are validated and trimmed at construction; raises
    `InvalidSchemeCodeError`.
    """

    scheme: str
    code: str
    severity_label: str = ""

    def __post_init__(self) -> None:
        # Loop var named `attr_name` (not `field_name`) to avoid shadowing the
        # `dataclasses.field` import at module top.
        for attr_name, value, max_length in (
            ("scheme", self.scheme, SCHEME_CODE_SCHEME_MAX_LENGTH),
            ("code", self.code, SCHEME_CODE_CODE_MAX_LENGTH),
        ):
            trimmed = value.strip()
            if not trimmed or len(trimmed) > max_length:
                raise InvalidSchemeCodeError(attr_name, value, max_length)
            object.__setattr__(self, attr_name, trimmed)
        # severity_label is allowed empty (some schemes encode severity in the
        # code itself); if non-empty, length-bound. Whitespace-only strips to
        # empty silently, matching GHSPictogram's empty-set-OK semantic.
        sev_trimmed = self.severity_label.strip()
        if len(sev_trimmed) > SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH:
            raise InvalidSchemeCodeError(
                "severity_label",
                self.severity_label,
                SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH,
            )
        object.__setattr__(self, "severity_label", sev_trimmed)


# ---------------------------------------------------------------------------
# The discriminated union
# ---------------------------------------------------------------------------

HazardClassification = NFPA704Rating | RiskBand | GHSPictogram | SchemeCode
"""The four-arm discriminated union of intrinsic hazard descriptors.

Used as the typed value carried by `HazardDeclaration.classifications` on
the Safety BC's Clearance aggregate. Type-narrowed by `match`/`isinstance`
at the boundary (Pydantic at the API, payload-shape check at the evolver).
"""


__all__ = [
    "GHS_PICTOGRAM_MAX_CODE",
    "GHS_PICTOGRAM_MIN_CODE",
    "GHS_STATEMENT_CODE_MAX_LENGTH",
    "GHS_VALID_PICTOGRAMS",
    "NFPA704_MAX_RATING",
    "NFPA704_MIN_RATING",
    "NFPA704_VALID_SPECIAL",
    "SCHEME_CODE_CODE_MAX_LENGTH",
    "SCHEME_CODE_SCHEME_MAX_LENGTH",
    "SCHEME_CODE_SEVERITY_LABEL_MAX_LENGTH",
    "GHSPictogram",
    "HazardClassification",
    "InvalidGHSPictogramCodeError",
    "InvalidGHSStatementCodeError",
    "InvalidNFPA704RatingError",
    "InvalidNFPA704SpecialError",
    "InvalidSchemeCodeError",
    "NFPA704Rating",
    "RiskBand",
    "SchemeCode",
]
