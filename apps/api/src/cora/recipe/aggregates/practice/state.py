"""Practice aggregate state, value objects, status enum, and domain errors.

`Practice` is the **facility-adapted Method** — the institution's
curated version of a technique class, ready to bind to specific
Asset instances at Plan time. ISA-88 maps it to **Site Recipe**:
the Method (≈ General Recipe) gets adapted at the Site level with
facility-specific equipment, constraints, and operational defaults,
but is still abstract over which specific batch run it serves.

Per the BC map's recipe ladder:
  - Method ≈ General Recipe (vendor / scientific community)
  - **Practice ≈ Site Recipe** (this aggregate)
  - Plan ≈ Master / Control Recipe (concrete Asset binding)
  - Run ≈ batch execution


Minimal Practice:
  - `id` + `name`
  - `method_id: UUID` — the Method this Practice adapts (eventual-
    consistency stance: existence is NOT verified at decide time;
    same precedent as Method.needed_family_ids and Trust Conduit zone refs)
  - `site_id: UUID` — the Site-level Asset this Practice belongs to
    (institutional ownership; eventual-consistency: not verified)
  - `status: PracticeStatus` (Defined → Versioned → Deprecated FSM)
  - `version: str | None` (None until first version_practice)

Additional facets are deferred if pilot demand emerges:
  - `additional_families: frozenset[FamilyId]` (facility-
    specific Family requirements that go beyond Method's
    needed_family_ids — for example a facility that always pairs
    Tomography with FlyScan)
  - `default_parameters` (parameter envelope dict)
  - `safety_overlay` (free-text or structured operator instructions)
  - `owner` (Actor id; institutional sanctioning authority)

## Why Practice and not just Method.facility_id

ISA-88's Site Recipe layer exists for a reason: a single General
Recipe can have multiple facility-adapted Practices (different
sites, different vendors, different operational defaults), and they
evolve independently. Pinning facility constraints onto Method
itself would force a 1-Method-per-facility model that doesn't
generalize.

## Eventual-consistency stance for cross-aggregate refs

Same precedent as everywhere else (Trust Conduit zone refs,
Method needed_family_ids, Asset.family_ids entries):
the decider does NOT verify `method_id` refers to a real
Method or `site_id` refers to a real Site-level Asset. Typos
produce "dangling" Practices; downstream Plan binding is where
the mismatch surfaces.

## Status as enum-in-state, derived-from-event-type-in-evolver

Same precedent as Method and Family. The lifecycle
mirrors Method's: Defined → Versioned → Deprecated.

## Ninth bounded-name VO

`PracticeName` is the **ninth** trimmed-bounded-name VO after
Actor / Zone / Conduit / Policy / Subject / Family / Asset /
Method. The shared trim+length-check logic was hoisted to
`cora.shared.bounded_text.validate_bounded_text` once the
10th VO (PlanName) landed; PracticeName now calls that helper
while keeping its own frozen dataclass type and per-aggregate
error class.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import bounded_name

PRACTICE_NAME_MAX_LENGTH = 200
PRACTICE_VERSION_TAG_MAX_LENGTH = 50


class PracticeStatus(StrEnum):
    """The Practice's lifecycle state.

    Mirrors Method's lifecycle (and Family's). Transitions land
    per-slice:
      - Defined -> Versioned        (version_practice)
      - (Defined | Versioned) -> Deprecated  (deprecate_practice)

    `Defined` is the genesis state set by `define_practice`. The
    enum values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidPracticeNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Practice name must be 1-{PRACTICE_NAME_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class PracticeAlreadyExistsError(Exception):
    """Attempted to define a practice whose stream already has events."""

    def __init__(self, practice_id: UUID) -> None:
        super().__init__(f"Practice {practice_id} already exists")
        self.practice_id = practice_id


class PracticeNotFoundError(Exception):
    """Attempted an operation on a practice whose stream has no events."""

    def __init__(self, practice_id: UUID) -> None:
        super().__init__(f"Practice {practice_id} not found")
        self.practice_id = practice_id


class PracticeCannotVersionError(Exception):
    """Attempted to version a practice not in `Defined` or `Versioned`.

    Multi-source guard: `version_practice` accepts both `Defined`
    (first revision) and `Versioned` (subsequent revisions). Only
    `Deprecated` is rejected. Same divergence from strict-not-
    idempotent as version_method / version_family:
    re-versioning with the same tag succeeds (re-attestation is a
    legitimate audit moment).

    Per-transition error class — same naming convention as
    `MethodCannotVersionError` (Recipe BC) and
    `FamilyCannotVersionError` (Equipment BC).
    """

    def __init__(self, practice_id: UUID, current_status: "PracticeStatus") -> None:
        super().__init__(
            f"Practice {practice_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{PracticeStatus.DEFINED.value} or {PracticeStatus.VERSIONED.value}"
        )
        self.practice_id = practice_id
        self.current_status = current_status


class PracticeCannotDeprecateError(Exception):
    """Attempted to deprecate a practice not in `Defined` or `Versioned`.

    Multi-source guard. Re-deprecating an already-`Deprecated`
    practice raises (strict-not-idempotent). Mirrors
    MethodCannotDeprecateError shape.
    """

    def __init__(self, practice_id: UUID, current_status: "PracticeStatus") -> None:
        super().__init__(
            f"Practice {practice_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{PracticeStatus.DEFINED.value} or {PracticeStatus.VERSIONED.value}"
        )
        self.practice_id = practice_id
        self.current_status = current_status


class InvalidPracticeVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error so direct in-process
    callers (sagas, tests) get the same protection. Same precedent as
    InvalidMethodVersionTagError (Recipe BC) and
    InvalidFamilyVersionTagError (Equipment BC).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Practice version tag must be 1-{PRACTICE_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


@bounded_name(max_length=PRACTICE_NAME_MAX_LENGTH, error_class=InvalidPracticeNameError)
@dataclass(frozen=True)
class PracticeName:
    """Display name for a practice. Trimmed; 1-200 chars.

    Ninth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `bounded_name` decorator (see
    `cora.shared.bounded_text`).
    """

    value: str


@dataclass(frozen=True)
class Practice:
    """Aggregate root: a facility-adapted Method (ISA-88 Site Recipe analog).

    `method_id` is the Method this Practice adapts. `site_id` is the
    Site-level Asset (per Equipment's hierarchy) this Practice
    belongs to. Both are eventual-consistency refs: the decider does
    NOT verify they refer to real aggregates. Mismatch surfaces at
    Plan binding.

    `version` mirrors Method's pattern: None until the first
    version_practice call; preserved across deprecation as the audit
    signal of the last revision before deprecation. State always holds
    the latest tag — past tags live in the event stream as
    `PracticeVersioned` events. No `current_` prefix because state by
    definition holds current values (same convention as `status`,
    `name`).
    """

    id: UUID
    name: PracticeName
    method_id: UUID
    site_id: UUID
    status: PracticeStatus = PracticeStatus.DEFINED
    version: str | None = None
