"""Pure decider for the `DefineCalibration` command.

Genesis-style decider: produces a `CalibrationDefined` event for a
fresh stream. Identity-tuple uniqueness (no two Calibrations with the
same `(target_id, quantity, operating_point)`) is enforced
via Postgres `jsonb` UNIQUE constraint on `proj_calibration_summary`
at projection write time per Q6 lock; the decider does NOT pre-check
the projection (deferred until pilot shows operator pain or duplicate
incidents accumulate; tracked as watch item).

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most fundamental
issues surface first:

  1. State must be None (genesis-only) → `CalibrationAlreadyExistsError`
     (stream-level genesis collision; distinct from identity-tuple
     uniqueness which is projection-enforced).
  2. `operating_point` validated STRICT against the quantity's
     `OPERATING_POINT_SCHEMA` via
     `validate_values_against_schema(no_schema_message=...)`.
     Schema is always present (CalibrationQuantity is closed enum;
     registry guarantees every value has a schema). Non-empty dict
     against schema runs jsonschema-rs Draft 2020-12 with `iter_errors`;
     first violation raises `InvalidOperatingPointError`. Empty dict
     against schema with required fields raises (required-field check
     at this layer per 6g-c precedent for `effective_parameters`).
  3. `description` (when not None and not empty-after-trim) wrapped via
     `CalibrationDescription`; 0-2000 chars → `InvalidCalibrationDescriptionError`.

Initial revision list is empty; the genesis event carries identity +
operating_point + description only. Revisions arrive via subsequent
`append_calibration_revision` slice calls.

`defined_by` is handler-injected from the request envelope's
`principal_id` (not on the command). At define time author and
principal are equal by construction.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationAlreadyExistsError,
    CalibrationDefined,
    CalibrationDescription,
    InvalidOperatingPointError,
    reject_empty_against_required,
)
from cora.calibration.features.define_calibration.command import DefineCalibration
from cora.calibration.quantities import get_operating_point_schema
from cora.shared.identity import ActorId
from cora.shared.json_schema_validation import validate_values_against_schema


def decide(
    state: Calibration | None,
    command: DefineCalibration,
    *,
    now: datetime,
    new_id: UUID,
    defined_by: ActorId,
) -> list[CalibrationDefined]:
    """Decide the events produced by defining a new Calibration.

    Invariants:
      - State must be None (genesis-only)
        -> CalibrationAlreadyExistsError
      - operating_point must validate STRICT against the quantity's
        OPERATING_POINT_SCHEMA -> InvalidOperatingPointError
      - Description (when set and non-empty after trim) must be valid
        -> InvalidCalibrationDescriptionError
        (via CalibrationDescription VO)
    """
    if state is not None:
        raise CalibrationAlreadyExistsError(state.id)

    # STRICT schema validation: every CalibrationQuantity has a registered
    # operating_point_schema (closed enum + registry invariant). Empty
    # operating_point against a schema with `required` keys is rejected.
    operating_point_schema = get_operating_point_schema(command.quantity)
    _validate_operating_point(command.operating_point, operating_point_schema)

    # Description: trim + bound-check only when supplied; treat empty-
    # after-trim as None / absent per the design memo open-question lean.
    trimmed_description = _coerce_description(command.description)

    return [
        CalibrationDefined(
            calibration_id=new_id,
            target_id=command.target_id,
            quantity=command.quantity.value,
            operating_point=command.operating_point,
            description=trimmed_description,
            defined_by=defined_by,
            occurred_at=now,
        )
    ]


def _validate_operating_point(operating_point: dict[str, Any], schema: dict[str, Any]) -> None:
    """Strict validation of operating_point against the quantity's schema.

    The schema is always non-None (closed enum + registry); we wrap
    the shared validator with the BC-specific error class.
    """
    validate_values_against_schema(
        operating_point,
        schema,
        error_class=InvalidOperatingPointError,
        no_schema_message=(
            "operating_point cannot be validated without a registered schema "
            "(quantity registry invariant violated: keys={keys})"
        ),
    )
    reject_empty_against_required(operating_point, schema, error_class=InvalidOperatingPointError)


def _coerce_description(value: str | None) -> str | None:
    """Trim + bound-check description if supplied; empty-after-trim → None."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    # Wrap via the VO to enforce max-length + raise the named error.
    return CalibrationDescription(value).value


# Re-exports to keep the slice's public surface contained
__all__ = ["decide"]
