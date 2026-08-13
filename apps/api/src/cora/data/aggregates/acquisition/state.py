"""Acquisition aggregate state, status enum, and domain errors.

An `Acquisition` is the birth-certificate fact that a producing Asset
captured bytes into a Dataset under an optional Run context. It is a
slim recorded-fact-chain: one stream per Acquisition, exactly one
event ever (`AcquisitionRecorded`), terminal at genesis. State IS the
event-folded value (slim-aggregate rule).

## What an Acquisition is NOT

  - Not the bytes (those live wherever the produced Dataset's URI
    points)
  - Not the Dataset (the Dataset is the logical product; the
    Acquisition records the act of capturing it)
  - Not an editable record: a flawed Acquisition is corrected by
    recording a NEW Acquisition, not by mutating the old one
    (fact-chain semantic)

## Dual-time pattern

`captured_at` and `recorded_at` are BOTH first-class state fields
with distinct semantic:

  - `captured_at`: caller-asserted provenance about when the physical
    capture happened at the instrument (instrument wall-clock).
  - `recorded_at`: CORA-side wall-clock when `record_acquisition` ran
    (the in-memory state field maps to the event's `occurred_at`
    payload key per the CORA transversal-time convention).

`captured_at` MAY legitimately precede `recorded_at` by hours or days
(operator backfills from an offline acquisition host, post-hoc
reprocessor registration, EPICS replay). The decider does NOT enforce
`captured_at <= recorded_at`; it only rejects a `captured_at` that is
in the future relative to `recorded_at + skew_tolerance`.

## Cross-aggregate bindings

  - `producing_asset_id` REQUIRED: the capturing Asset. Its Family
    MUST declare the Capturing affordance (gate at decider time).
  - `dataset_id` REQUIRED: the logical Dataset this capture produced.
  - `producing_run_id` OPTIONAL (None for calibration / dark-field /
    autonomous-agent standalone captures with no Run context).

## Attribution

A single `recorded_by: ActorId` carries the every-fact-has-an-actor
obligation. The PHYSICAL capturing entity is the `producing_asset_id`
(a device, not an actor); only the act of RECORDING the fact into
CORA needs an ActorId. Capture-port-driven recordings carry the
system principal; operator-initiated registrations carry the
operator's ActorId.

## Settings and evidence

`settings` is a carrier dict validated for primitive-leaf shape
today; per-Family schema validation against the producing Asset's
Family.settings_schema is deferred. No real writer populates it with
anything beyond ad hoc test fixtures (`ingest_scan` always sends
`{}`), so there is no real shape yet to type; forcing a VO onto zero
production data would be inventing structure ahead of the operator
demand the module already says it is waiting for. Revisit when a
Family.settings_schema exists to type against.

`evidence` is `AcquisitionEvidence`, not a freeform dict: it carries
the one real shape a writer produces today (`ingest_scan`'s frame
accounting), so the record exporter's generated disposition table can
resolve `projection_count`, the angle range, and `captured_at_source`
field by field instead of dropping the whole carrier opaque. See
`AcquisitionEvidence` and `validate_evidence` for the shape and the
writer-unification this replaced (`ingest_scan.EVIDENCE_SCHEMA`, a
JSON-schema copy of the same rules enforced a second time).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from cora.shared.identity import ActorId

# Allowed leaf types inside the settings / evidence carrier dicts.
# Shape-only validation today: the values must be JSON-primitives or
# nested containers of them. Per-Family schema validation lands later.
_PRIMITIVE_LEAF_TYPES = (str, int, float, bool, type(None))


class AcquisitionStatus(StrEnum):
    """The Acquisition's lifecycle state.

    Ships day-one with exactly one value (`RECORDED`). Kept as a
    StrEnum (not a constant) for symmetry with every other CORA
    aggregate and the BC-status-vocabulary fitness test. Member name
    is SCREAMING_SNAKE per Python StrEnum convention; the string value
    is PascalCase per the BC-status-vocabulary fitness expectation.

    An Acquisition is terminal at genesis: there is no further
    transition. A flawed capture is corrected by recording a new
    Acquisition, not by mutating this one.
    """

    RECORDED = "Recorded"


class InvalidAcquisitionCapturedAtError(ValueError):
    """The supplied captured_at is not a timezone-aware datetime or is
    in the future beyond the clock-skew tolerance.

    `captured_at` MAY precede `recorded_at` by any amount (backfills
    are legitimate); only the upper bound is checked. The bound is
    `recorded_at + skew_tolerance` (a small default for clock-skew
    safety, supplied from the handler so the decider stays pure).

    Mapped to HTTP 400.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Acquisition captured_at invalid: {reason}")
        self.reason = reason


class InvalidAcquisitionSettingsError(ValueError):
    """The supplied settings dict has a malformed shape.

    Shape-only check today: settings must be a mapping whose leaves
    are JSON-primitives (or nested lists / dicts of them). Per-Family
    schema validation against the producing Asset's Family.settings_schema
    is deferred. Symmetric pair with the evidence shape check.

    Mapped to HTTP 400.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Acquisition settings invalid: {reason}")
        self.reason = reason


class InvalidAcquisitionEvidenceError(ValueError):
    """The supplied evidence dict does not fit `AcquisitionEvidence`.

    Raised for an unknown key, a wrong-typed value, or a
    `captured_at_source` outside `CapturedAtSource`. See
    `validate_evidence`, the sole declarer of the shape.

    Mapped to HTTP 400.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Acquisition evidence invalid: {reason}")
        self.reason = reason


class AcquisitionAlreadyExistsError(Exception):
    """Attempted to record an Acquisition whose stream already has events.

    Genesis-only same-stream-id guard (strict-not-idempotent). There
    is NO cross-stream uniqueness on (dataset_id, producing_asset_id,
    captured_at): legitimate re-captures and rapid-fire detector
    frames per Dataset are first-class.

    Mapped to HTTP 409.
    """

    def __init__(self, acquisition_id: UUID) -> None:
        super().__init__(f"Acquisition {acquisition_id} already exists")
        self.acquisition_id = acquisition_id


class AcquisitionAssetNotFoundError(Exception):
    """The producing_asset_id does not resolve to a known Asset.

    Handler-side `AssetLookup.lookup(producing_asset_id)` returned
    None. Data-BC-local class (not reused from Equipment BC; the
    rule-of-three for class sharing requires three consumers with
    identical semantics).

    Mapped to HTTP 404.
    """

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"Cannot record Acquisition: producing_asset_id {asset_id} does not exist")
        self.asset_id = asset_id


class AcquisitionRunNotFoundError(Exception):
    """The producing_run_id (when non-null) does not resolve to a known Run.

    Only fires when `producing_run_id is not None` and the handler's
    Run pre-load returns no events. Data-BC-local class (NOT reused
    from Dataset's ProducingRunNotFoundError: Acquisition is a
    fact-chain and Dataset is an instance, so binding-semantics differ;
    the rule-of-three for class sharing requires three consumers).

    Mapped to HTTP 404.
    """

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Cannot record Acquisition: producing_run_id {run_id} does not exist")
        self.run_id = run_id


class AcquisitionCannotRecordWithoutCapturingError(Exception):
    """The producing Asset's Family does not declare the Capturing affordance.

    The handler-loaded `AssetLookupResult.family_affordances` does not
    contain "Capturing". The producing Asset MUST be able to produce a
    Data BC Acquisition fact on capture. Named in the canonical
    `<X>Cannot<Verb>Error` state-transition family; the "Capturing"
    token keeps the R2 symmetry with the enum value `CAPTURING`.

    Mapped to HTTP 409 (business-invariant violation; the route shape
    is valid).
    """

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(
            f"Cannot record Acquisition: producing Asset {asset_id} does not declare "
            f"the Capturing affordance"
        )
        self.asset_id = asset_id


class CapturedAtSource(StrEnum):
    """Which of the file's candidate timestamps `captured_at` came from.

    A layout can offer several timestamps and a deployment's writer can
    be wrong about one of them: 2-BM's `start_date` is measurably the
    PREVIOUS scan's end, while its `end_date` is correct to within
    seconds (see `ScanReader.Description.captured_at_source`'s own
    docstring). The published record needs to say which one it
    believed rather than leave a reader to assume.

    `Description.captured_at_source` is deliberately a plain `str` at
    the port so a future layout can name a timestamp no reader has
    produced yet; that is a port-level extensibility promise this enum
    does not honor. It does not narrow anything new, though:
    `ingest_scan.EVIDENCE_SCHEMA` already closed this same set via a
    JSON-schema enum before this VO existed, so a layout naming a
    fourth source already refused evidence before this change, just
    with a JSON-schema error instead of this enum's ValueError. A
    layout that legitimately needs a fourth name must widen this enum
    in the same change, or ingest keeps refusing it.
    """

    START_DATE = "start_date"
    END_DATE = "end_date"
    OPERATOR = "operator"


@dataclass(frozen=True)
class AcquisitionEvidence:
    """Frame accounting and provenance for one recorded capture.

    Declares the one real shape a writer produces today (`ingest_scan`,
    the 2-BM pilot's scan ingest): frame counts by role, the projection
    angle range, and which of the file's timestamps was believed.
    Supersedes `ingest_scan.EVIDENCE_SCHEMA`, a JSON-schema copy of the
    same rules enforced a second time at the ingest boundary; this VO
    is now the sole declarer, checked once by `validate_evidence` on
    both the `ingest_scan` and direct `record_acquisition` write paths.

    Every field is independently optional: 0 means verified-none, None
    means the source cannot know, and a consumer must not collapse the
    two (mirrors `ScanReader.Description`'s own zero-versus-None
    convention). `AcquisitionEvidence()`, every field None, is the "no
    evidence supplied" state, replacing the old empty-dict `{}`
    sentinel; the wire rendering is the same empty JSON object either
    way (see `to_payload`).

    Declared directly on `AcquisitionRecorded` (not degraded to `dict`
    first) so the record exporter's generator recurses into it field by
    field instead of dropping the whole carrier opaque; see
    `docs/reference/modeling.md`'s event-VO carve-out. This does NOT
    make it a `ClosedValueObject`: `reader_kind`, `checksum_computer_kind`
    and `captured_at_raw` are open-vocabulary strings with no closed
    range (a new adapter, or a new file layout, can introduce a value
    this VO has never seen), so they recurse and drop like any other
    free text, the same posture as `DatasetEncoding`'s `media_type`.
    Only `captured_at_source` closes, via `CapturedAtSource`.

    Unlike `DatasetChecksum` / `DatasetEncoding`, this VO has no
    `__post_init__`: it is a plain typed carrier, not self-validating.
    `validate_evidence` is what actually enforces the shape (unknown
    keys, wrong types, a closed `captured_at_source`); constructing
    `AcquisitionEvidence(...)` directly bypasses all of it, the same
    way constructing a dataclass always bypasses a validator that
    lives outside `__init__`. Every real call site goes through
    `validate_evidence`; direct construction is for tests only.

    `projection_angle_first` / `projection_angle_last` are degrees
    (canonical unit; see `ScanReader.Description.projection_angles_deg`),
    a fact the deleted `ingest_scan.EVIDENCE_SCHEMA` carried as a
    `"unit"` JSON-schema annotation that was never functionally
    enforced (no validator read it) and has no equivalent here beyond
    this sentence.
    """

    reader_kind: str | None = None
    checksum_computer_kind: str | None = None
    captured_at_source: CapturedAtSource | None = None
    captured_at_raw: str | None = None
    projection_count: int | None = None
    flat_count: int | None = None
    dark_count: int | None = None
    invalid_count: int | None = None
    commanded_projection_count: int | None = None
    commanded_flat_count: int | None = None
    commanded_dark_count: int | None = None
    dropped_frame_count: int | None = None
    projection_angle_count: int | None = None
    projection_angle_first: float | None = None
    projection_angle_last: float | None = None


_EVIDENCE_STR_FIELDS = ("reader_kind", "checksum_computer_kind", "captured_at_raw")
_EVIDENCE_INT_FIELDS = (
    "projection_count",
    "flat_count",
    "dark_count",
    "invalid_count",
    "commanded_projection_count",
    "commanded_flat_count",
    "commanded_dark_count",
    "dropped_frame_count",
    "projection_angle_count",
)
_EVIDENCE_FLOAT_FIELDS = ("projection_angle_first", "projection_angle_last")
_EVIDENCE_KNOWN_KEYS = frozenset(
    {"captured_at_source", *_EVIDENCE_STR_FIELDS, *_EVIDENCE_INT_FIELDS, *_EVIDENCE_FLOAT_FIELDS}
)


def _validate_carrier_shape(value: Any, *, label: str, depth: int = 0) -> None:
    """Recursively check that a carrier dict has only primitive leaves.

    Used by settings only (evidence has its own `AcquisitionEvidence`
    shape, see `validate_evidence`). Raises ValueError with a
    `label`-prefixed reason on the first malformed leaf; the caller
    wraps that into the field-specific Invalid* error class.
    """
    if depth > 32:
        raise ValueError(f"{label} nests too deeply")
    if isinstance(value, _PRIMITIVE_LEAF_TYPES):
        return
    if isinstance(value, Mapping):
        mapping = cast("Mapping[Any, Any]", value)
        for key, sub in mapping.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} keys must be strings (got {type(key).__name__})")
            _validate_carrier_shape(sub, label=label, depth=depth + 1)
        return
    if isinstance(value, (list, tuple)):
        sequence = cast("list[Any] | tuple[Any, ...]", value)
        for sub in sequence:
            _validate_carrier_shape(sub, label=label, depth=depth + 1)
        return
    raise ValueError(f"{label} has a non-primitive leaf of type {type(value).__name__}")


def validate_settings(value: dict[str, Any]) -> dict[str, Any]:
    """Validate the settings carrier dict for primitive-leaf shape.

    Shape-only today (per-Family schema validation is deferred). The
    top level must be a dict keyed by strings; leaves must be
    JSON-primitives or nested containers of them.
    """
    if not isinstance(value, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise InvalidAcquisitionSettingsError(f"must be a dict (got {type(value).__name__})")
    try:
        _validate_carrier_shape(value, label="settings")
    except ValueError as exc:
        raise InvalidAcquisitionSettingsError(str(exc)) from exc
    return value


def _validate_evidence_field(value: Any, expected: type, key: str) -> Any:
    """Type-check one evidence leaf, rejecting `bool` where `int` is expected
    (JSON's `integer` and `boolean` are distinct types; Python's is not)."""
    if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
        raise InvalidAcquisitionEvidenceError(
            f"{key} must be a {expected.__name__} (got {type(value).__name__})"
        )
    return value


def validate_evidence(value: dict[str, Any]) -> AcquisitionEvidence:
    """Validate a caller-supplied dict and build the `AcquisitionEvidence` VO.

    Sole declarer of evidence's shape (see `AcquisitionEvidence`).
    Every key is optional; an unknown key, a wrong-typed value, or a
    `captured_at_source` outside `CapturedAtSource` all raise
    `InvalidAcquisitionEvidenceError`. An empty dict is valid and
    returns `AcquisitionEvidence()` ("no evidence supplied").

    Used on both write paths: `record_acquisition`'s decider calls this
    on the caller-supplied dict; `from_stored` calls it again on the
    same dict shape read back off the wire, so a corrupted stored
    payload surfaces as `Malformed AcquisitionRecorded` rather than
    silently reconstructing something the aggregate never actually
    validated. Matches `DatasetChecksum` / `DatasetEncoding`'s pattern
    of reusing one validator on both paths, though unlike them the
    validation lives here rather than in `AcquisitionEvidence.__post_init__`
    (see that class's docstring).

    A rejection here (e.g. an unrecognized `captured_at_source`) embeds
    the specific bad key or value in its message. Raised from the
    decider that is the caller's own just-submitted value echoed back
    to them, not a leak. Raised from `from_stored` on an already-stored
    payload, this reproduces the same pattern `InvalidDatasetChecksumError`
    already has on that path (`f"...value={value!r}"`, wrapped into
    `Malformed DatasetRegistered payload` by the identical
    `deserialize_or_raise(..., extra=(ValueError,))` mechanism) rather
    than introducing a new one; `event_payload.py`'s no-payload-echo
    convention protects the RAW PAYLOAD DICT from appearing in the
    wrapper message, not the wrapped exception's own text. Scrubbing
    that residual (across every VO reusing a validator this way, not
    only this one) is an open campaign-wide question, not something to
    special-case here.
    """
    if not isinstance(value, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise InvalidAcquisitionEvidenceError(f"must be a dict (got {type(value).__name__})")
    unknown = set(value) - _EVIDENCE_KNOWN_KEYS
    if unknown:
        raise InvalidAcquisitionEvidenceError(f"unknown key(s): {sorted(unknown)}")

    kwargs: dict[str, Any] = {}
    for key in _EVIDENCE_STR_FIELDS:
        if key in value:
            kwargs[key] = _validate_evidence_field(value[key], str, key)
    for key in _EVIDENCE_INT_FIELDS:
        if key in value:
            kwargs[key] = _validate_evidence_field(value[key], int, key)
    for key in _EVIDENCE_FLOAT_FIELDS:
        if key in value:
            raw = value[key]
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise InvalidAcquisitionEvidenceError(
                    f"{key} must be a number (got {type(raw).__name__})"
                )
            kwargs[key] = float(raw)
    if "captured_at_source" in value:
        raw_source = _validate_evidence_field(
            value["captured_at_source"], str, "captured_at_source"
        )
        try:
            kwargs["captured_at_source"] = CapturedAtSource(raw_source)
        except ValueError as exc:
            allowed = sorted(source.value for source in CapturedAtSource)
            raise InvalidAcquisitionEvidenceError(
                f"captured_at_source must be one of {allowed} (got {raw_source!r})"
            ) from exc
    return AcquisitionEvidence(**kwargs)


@dataclass(frozen=True, slots=True)
class Acquisition:
    """Aggregate root: one recorded capture fact.

    All fields are set-once at genesis and immutable. Per-Acquisition
    streams are exactly one event long; state IS the event-folded
    value (slim-aggregate rule).

    `recorded_at` is the CORA-side wall-clock (maps to the event's
    `occurred_at` payload key); `captured_at` is the instrument
    wall-clock carried as a separate first-class field.
    """

    id: UUID
    dataset_id: UUID
    producing_asset_id: UUID
    producing_run_id: UUID | None
    captured_at: datetime
    settings: dict[str, Any]
    evidence: AcquisitionEvidence
    recorded_at: datetime
    recorded_by: ActorId
    status: AcquisitionStatus = field(default=AcquisitionStatus.RECORDED)
