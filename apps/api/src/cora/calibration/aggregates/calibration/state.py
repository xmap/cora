"""Calibration aggregate state, enums, polymorphic source union, and domain errors.

A `Calibration` is an empirical record of an instrument value (rotation
center, detector pixel size, beam alignment) keyed by
`(target_id, quantity, operating_point)`. Per
[[project_calibration_design]], revisions accumulate append-only on
the aggregate; status lives per-revision; no aggregate-level FSM
transitions.

Key invariants:

  - Identity tuple uniqueness via Postgres jsonb `=` on the projection
    (Q6 lock; key-order normalized + numeric value-equality `25 == 25.0`
    for free; NXcalibration cautionary tale on free-dict at the contract
    layer drove closed JSON Schema per quantity).
  - Revisions are immutable; corrections produce new revisions with
    explicit `supersedes_revision_id` (CMS lesson; in-place mutation
    breaks reproducibility for every prior consumer).
  - Source is a tagged union `MeasuredSource | ComputedSource |
    AssertedSource` (Q5 lock; GitHub-webhook + Postgres-exclusive-arc
    consensus against untyped polymorphism).

## Status orthogonal to source

`CalibrationStatus` is a 2-tier ladder (provisional / verified). The
source kind (MEASURED / COMPUTED / ASSERTED) is derived from
`type(revision.source)` — NOT a redundant flat enum on the revision
(Q5 lock). Status and source give a 2x3 matrix that's strictly more
expressive than CMS's flat 3-tier; tier expansion to add `refined`
deferred until a PCL-shaped middle latency window emerges in pilot use.

## VO pattern reuse

`CalibrationDescription` is a 0-2000 char trimmed optional string
(matches Method/Plan/Family/Practice precedent). Body fields ride
through bounded-text validation; the helper is hoisted at
`cora.infrastructure.bounded_text`.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

CALIBRATION_DESCRIPTION_MAX_LENGTH = 2000


class CalibrationStatus(StrEnum):
    """A revision's confidence tier for downstream consumption.

    Two values:

      - `Provisional` -- initial estimate or early-data-derived figure;
                         downstream consumers may still use it but
                         should be aware it is unblessed.
      - `Verified`    -- blessed for production reconstructions /
                         analyses; downstream consumers can rely on it
                         without operator follow-up.

    2-tier matches when no PCL-shaped middle latency window exists with
    distinct statistical maturity (ERA5 reanalysis precedent). 3-tier
    (CMS Express/Prompt/ReReco pattern) is deferred to phase 12f when
    refined-after-provisional becomes a frequent structured workflow.
    """

    PROVISIONAL = "Provisional"
    VERIFIED = "Verified"


# ---------------------------------------------------------------------------
# Polymorphic source — discriminated union (Q5 lock)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeasuredSource:
    """Revision value was derived from an alignment Procedure.

    The Procedure measured the value (operator sphere-centroid,
    live-tomostream readout, motor-encoder reading). The Procedure id
    is carried for PROV-O `wasGeneratedBy` provenance.
    """

    procedure_id: UUID


@dataclass(frozen=True)
class ComputedSource:
    """Revision value was extracted by numerical analysis of a Dataset.

    Examples: `tomopy.find_center_vo` extracted a refined rotation
    center; flat-field correction derived from a flat baseline Dataset.
    The Dataset id is carried for PROV-O `wasDerivedFrom` provenance.
    The same Dataset's reconstruction may then cite the *refined*
    revision; the AsShot anchor on Run.pinned_calibration_ids stays unchanged.
    """

    dataset_id: UUID


@dataclass(frozen=True)
class AssertedSource:
    """Revision value was typed directly by an operator.

    No automated derivation step; the operator asserted the value from
    memory, vendor datasheet, or out-of-band measurement. The Actor id
    is carried for accountability (the same identity is also on the
    StoredEvent envelope's principal_id, so this is denorm).
    """

    actor_id: UUID


type CalibrationSource = MeasuredSource | ComputedSource | AssertedSource
"""Three-arm discriminated union per Q5 lock.

Source kind is derived from `type(source)` at runtime; no redundant
`source_kind: StrEnum` field on the revision. Event-payload + projection
use exclusive-arc serialization (three nullable id columns + CHECK
constraint enforcing exactly-one-non-null) per Postgres-community
consensus.

Adding a fourth source kind = additive union extension + projection
column + serialize/deserialize helper update; declarative across the
codebase via Python's exhaustiveness checking under `assert_never`.
"""


# ---------------------------------------------------------------------------
# Domain validation errors
# ---------------------------------------------------------------------------


class InvalidCalibrationDescriptionError(ValueError):
    """The supplied description is whitespace-only or too long.

    `description` is OPTIONAL; this error fires only when a non-None
    value fails the trimmed-bounded-text contract (0-2000 chars after
    trimming; empty string treated as "absent" by the slice, not raised
    here).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Calibration description must be 0-{CALIBRATION_DESCRIPTION_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidCalibrationQuantityError(ValueError):
    """The supplied quantity string is not a registered CalibrationQuantity value.

    The closed StrEnum + per-quantity schema registry at
    `cora.calibration.quantities` enforces that every accepted quantity
    has declared operating_point_schema + value_schema. Unknown values
    are rejected at the API boundary before reaching the decider.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Unknown calibration quantity {value!r}; the CalibrationQuantity "
            f"closed catalog at cora.calibration.quantities does not include this value"
        )
        self.value = value


class InvalidOperatingPointError(ValueError):
    """The supplied operating_point fails the quantity's JSON Schema.

    Validated STRICT against the per-quantity operating_point_schema
    (additionalProperties: False; property types restricted to primitives
    per Q1 lock). Matches the `cora.infrastructure.json_schema_validation`
    error class shape used by Method.parameters_schema +
    Family.settings_schema.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidCalibrationValueError(ValueError):
    """The supplied value fails the quantity's value_schema.

    Same STRICT validation shape as InvalidOperatingPointError; per-
    quantity value_schema declares required + optional fields.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidCalibrationSourceError(ValueError):
    """Polymorphic source decoding / encoding error.

    Raised when an event-payload-shaped source dict fails the union
    discriminator (missing `kind`, unknown `kind` value, or the id
    field for the named arm is missing/malformed).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SupersedesRevisionNotFoundError(Exception):
    """`supersedes_revision_id` references a revision not in this aggregate.

    Cross-aggregate supersession is forbidden by design: a revision
    supersedes only siblings on the same Calibration (same quantity,
    same operating_point). Operators who need to re-baseline an
    operating point start a new Calibration.
    """

    def __init__(self, calibration_id: UUID, supersedes_revision_id: UUID) -> None:
        super().__init__(
            f"Calibration {calibration_id} has no revision {supersedes_revision_id} to supersede"
        )
        self.calibration_id = calibration_id
        self.supersedes_revision_id = supersedes_revision_id


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found)
# ---------------------------------------------------------------------------


class CalibrationAlreadyExistsError(Exception):
    """Attempted to define a calibration whose stream already has events.

    Per [[project_genesis_error_classes]] this class stays un-hoisted:
    per-BC isinstance routing in the BC's exception handler outweighs
    the ~80 LOC saved by hoisting to a generic `AggregateAlreadyExists`
    error.
    """

    def __init__(self, calibration_id: UUID) -> None:
        super().__init__(f"Calibration {calibration_id} already exists")
        self.calibration_id = calibration_id


class CalibrationNotFoundError(Exception):
    """Attempted an operation on a calibration whose stream has no events."""

    def __init__(self, calibration_id: UUID) -> None:
        super().__init__(f"Calibration {calibration_id} not found")
        self.calibration_id = calibration_id


class CalibrationIdentityAlreadyExistsError(Exception):
    """A Calibration with the same (target_id, quantity,
    operating_point) already exists.

    Detected via the projection's UNIQUE constraint on jsonb
    operating_point (Q6 lock: Postgres value-based equality including
    `25 == 25.0` + key-order + duplicate-key dedup). The aggregate
    layer raises this domain error before the unique-violation surfaces
    as a generic IntegrityError.
    """

    def __init__(
        self,
        target_id: UUID,
        quantity: str,
        operating_point: dict[str, Any],
    ) -> None:
        super().__init__(
            f"Calibration identity ({target_id}, {quantity}, {operating_point!r}) already exists"
        )
        self.target_id = target_id
        self.quantity = quantity
        self.operating_point = operating_point


# ---------------------------------------------------------------------------
# publish_revision domain errors
# ---------------------------------------------------------------------------


class CalibrationRevisionNotFoundError(Exception):
    """The named revision does not exist on this Calibration."""

    def __init__(self, calibration_id: UUID, revision_id: UUID) -> None:
        super().__init__(f"Calibration {calibration_id} has no revision {revision_id}")
        self.calibration_id = calibration_id
        self.revision_id = revision_id


class CalibrationCannotPublishRevisionError(Exception):
    """The named revision was appended before content_hash was kernel-fused.

    Legacy pre-rollout revisions carry `content_hash = None` per the
    additive-event pattern; publishing requires a deterministic
    artifact hash. Operators re-append the revision to populate the
    hash before retrying the publish.
    """

    def __init__(self, calibration_id: UUID, revision_id: UUID) -> None:
        super().__init__(
            f"Calibration {calibration_id} revision {revision_id} carries no content_hash; "
            f"re-append the revision to populate it before publishing"
        )
        self.calibration_id = calibration_id
        self.revision_id = revision_id


class OutboundPermitNotActiveError(Exception):
    """No Active outbound Permit authorizes publishing this artifact kind to the peer.

    Covers both "no Permit configured" (status surfaced as the
    sentinel `"<unresolved>"`) and "Permit exists but is not in
    the Active FSM position" (`Defined`, `Suspended`, or `Revoked`).
    The decider routes this to a single error class so operator
    diagnostics surface a uniform "configure or activate the
    outbound permit" message regardless of the underlying gap.
    """

    def __init__(
        self,
        peer_facility_id: str,
        artifact_kind: str,
        status: str,
    ) -> None:
        super().__init__(
            f"No Active outbound Permit for peer={peer_facility_id!r} "
            f"artifact_kind={artifact_kind!r} (current status={status!r})"
        )
        self.peer_facility_id = peer_facility_id
        self.artifact_kind = artifact_kind
        self.status = status


# ---------------------------------------------------------------------------
# Shared value-validation helper (used by both define_calibration and
# append_calibration_revision deciders)
# ---------------------------------------------------------------------------


def reject_empty_against_required(
    values: dict[str, Any],
    schema: dict[str, Any],
    *,
    error_class: type[ValueError],
) -> None:
    """Raise when `values` is empty AND `schema` declares required keys.

    `cora.infrastructure.json_schema_validation.validate_values_against_schema`
    accepts empty + non-None schema by design (required-field enforcement
    delegated to the per-aggregate consumer). For Calibration's
    `operating_point` and revision `value` dicts we want empty rejected:
    empty would either collide with another calibration on the UNIQUE
    constraint or produce a value-less revision.
    """
    if values:
        return
    raw_required = schema.get("required")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(raw_required, list) or not raw_required:  # pyright: ignore[reportUnknownArgumentType]
        return
    required = cast("list[str]", raw_required)  # pyright: ignore[reportUnknownArgumentType]
    msg = f"cannot be empty; the schema requires keys: {sorted(required)!r}"
    raise error_class(msg)


# ---------------------------------------------------------------------------
# Optional description VO (matches Method/Plan/Family precedent)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationDescription:
    """Free-form operator notes about this calibration. Trimmed; 0-2000 chars.

    Empty / whitespace-only inputs are NOT raised here — the slice
    layer treats empty-after-trim as None / absent. Only over-long
    values trigger the error.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=CALIBRATION_DESCRIPTION_MAX_LENGTH,
            error_class=InvalidCalibrationDescriptionError,
        )
        object.__setattr__(self, "value", trimmed)


# ---------------------------------------------------------------------------
# Revision value object (immutable; ordered list under aggregate.revisions)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationRevision:
    """One immutable entry in a Calibration's append-only revision list.

    `value` is a JSON-shaped dict validated against the owning
    quantity's value_schema at append time (STRICT; same schema-
    validated-values pattern as Method.parameters_schema).

    `source` is the polymorphic tagged union per Q5 lock; the source
    kind is `type(source).__name__` and the carried id field gives the
    PROV-O linkage target.

    `decided_by_decision_id` (OPTIONAL) mirrors the AdjustRun /
    StartRun / AbortRun pattern: a Decision BC record that justified
    appending this revision (operator pivot, agent advisory). NO
    cross-BC existence check at the decider.

    `supersedes_revision_id` (OPTIONAL) is a direct derivation edge
    pointing at a prior revision in the SAME aggregate that this
    revision supersedes. Direct edges save consumers a graph walk;
    traversal-only is rejected. Cross-aggregate supersession is
    forbidden: the supersedes target must exist in
    `aggregate.revisions` at append time.
    """

    revision_id: UUID
    value: dict[str, Any]
    status: CalibrationStatus
    source: CalibrationSource
    established_at: datetime
    established_by_actor_id: UUID
    decided_by_decision_id: UUID | None = None
    supersedes_revision_id: UUID | None = None
    # SHA-256 (64-char lowercase hex) of the canonical body bytes for
    # this revision's content subset; captured by append_calibration_revision per
    # the non-determinism principle and folded by the evolver from the
    # event payload. None for pre-rollout CalibrationRevisionAppended
    # events that landed before the field was added (additive-state
    # pattern; same convention as Method.content_hash and Plan.content_hash).
    # Each revision is immutable, so no preservation rules are needed:
    # the hash is set once when the revision is appended and never
    # rewritten. See [[project_content_addressed_identity_design]].
    content_hash: str | None = None

    def content_subset(self) -> dict[str, object]:
        """Canonical content subset hashed into CalibrationRevisionAppended.content_hash.

        Pins identity per [[project_content_addressed_identity_design]]:
        `value + status + source_kind + source_id + decided_by_decision_id
        + supersedes_revision_id`. Excluded: `revision_id` (identity, not
        content); `established_at` and `established_by_actor_id` (envelope
        metadata, analog of event `occurred_at` and `defined_by_actor_id`
        on Plan/Method); `content_hash` itself. The parent aggregate's
        identity (`target_id`, `quantity`, `operating_point`) lives one
        level up on the Calibration aggregate and is NOT folded into the
        revision-level hash — equivalence at the revision level means
        "same measured value via the same provenance," and consumers that
        want "same content for the same physical regime" compare
        (calibration_id, content_hash) at the projection.

        Source flattens from the exclusive-arc 3-field event-payload
        shape to a 2-field semantic shape (`source_kind` + `source_id`)
        so the hash represents meaning rather than wire layout. Mirrors
        the Plan-side flattening of `wires` from frozenset[Wire] to
        sorted 4-tuples-of-strings. UUIDs render as strings; status
        renders as its StrEnum value.
        """
        match self.source:
            case MeasuredSource(procedure_id=source_id):
                source_kind = "measured"
                source_id_str = str(source_id)
            case ComputedSource(dataset_id=source_id):
                source_kind = "computed"
                source_id_str = str(source_id)
            case AssertedSource(actor_id=source_id):
                source_kind = "asserted"
                source_id_str = str(source_id)
        return {
            "value": self.value,
            "status": self.status.value,
            "source_kind": source_kind,
            "source_id": source_id_str,
            "decided_by_decision_id": (
                str(self.decided_by_decision_id)
                if self.decided_by_decision_id is not None
                else None
            ),
            "supersedes_revision_id": (
                str(self.supersedes_revision_id)
                if self.supersedes_revision_id is not None
                else None
            ),
        }


# ---------------------------------------------------------------------------
# Calibration aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Calibration:
    """Aggregate root: an empirical instrument-value record.

    Slim aggregate per [[project_fold_cost_principles]]: identity +
    operating point + description + revision history + 3 timestamps.

    Identity is `(target_id, quantity, operating_point)`;
    aggregate uniqueness enforced via the projection's UNIQUE jsonb
    constraint (Q6 lock).

    `quantity` is stored as the raw StrEnum value-string rather than
    the enum object so legacy / pre-extension events stay loadable
    when new quantities land via PR. The slice + read helpers coerce
    to the closed enum at the read boundary.

    `operating_point` is a JSON-shaped dict (canonical form maintained
    by Postgres jsonb; primitive types only per the quantity schema's
    additionalProperties: False discipline).

    `revisions` is an append-only ordered tuple; new revisions are
    appended at the end. The latest revision per-status (or per-source-
    kind) is recomputed at read time via `read.py` helpers.

    Per the locked Path C convention (`project_template_aggregate_timestamps`),
    lifecycle bookkeeping timestamps (`defined_at`, `last_revised_at`)
    do NOT live on aggregate state; they are derived at projection-
    apply time from each event's envelope `occurred_at`. The 7th
    aggregate to follow the pattern. The `established_at` field on
    individual `CalibrationRevision` instances STAYS — it is the
    domain-meaningful timestamp of when the revision was decided
    (may legitimately differ from when the event was recorded).
    """

    id: UUID
    target_id: UUID
    quantity: str  # CalibrationQuantity value-string; coerced at read boundary
    operating_point: dict[str, Any]
    description: str | None
    revisions: tuple[CalibrationRevision, ...]
    defined_by_actor_id: UUID
