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
Family.settings_schema is deferred. `evidence` is a freeform
placeholder dict (primitive-leaf shape only); per-Family evidence
schemas are deferred until operator demand surfaces a distinct shape.
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
    """The supplied evidence dict has a malformed shape.

    Shape-only check today: evidence must be a mapping whose leaves
    are JSON-primitives (or nested lists / dicts of them). Per-Family
    evidence schemas are deferred. Symmetric pair with the settings
    shape check.

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


def _validate_carrier_shape(value: Any, *, label: str, depth: int = 0) -> None:
    """Recursively check that a carrier dict has only primitive leaves.

    Used by both settings and evidence. Raises ValueError with a
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


def validate_evidence(value: dict[str, Any]) -> dict[str, Any]:
    """Validate the evidence carrier dict for primitive-leaf shape.

    Shape-only today (per-Family evidence schemas are deferred). The
    top level must be a dict keyed by strings; leaves must be
    JSON-primitives or nested containers of them.
    """
    if not isinstance(value, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise InvalidAcquisitionEvidenceError(f"must be a dict (got {type(value).__name__})")
    try:
        _validate_carrier_shape(value, label="evidence")
    except ValueError as exc:
        raise InvalidAcquisitionEvidenceError(str(exc)) from exc
    return value


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
    evidence: dict[str, Any]
    recorded_at: datetime
    recorded_by: ActorId
    status: AcquisitionStatus = field(default=AcquisitionStatus.RECORDED)
