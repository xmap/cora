"""Shared JSON Schema validators for the schema-validated-values pattern.

CORA has two structurally identical validation surfaces across BCs:

  - **Schema declaration validators** check that a stored schema is
    well-formed and in CORA's constrained subset. Used at write time
    when an operator submits a new schema (Family.settings_schema
    via 5g-a's `update_family_settings_schema`; Method.parameters_schema
    via 6g-a's `update_method_parameters_schema`).
  - **Values-against-schema validators** check that a values dict
    conforms to a previously-declared schema. Used when the values
    are written (Plan.default_parameters via 6g-b; Run.effective_parameters
    via 6g-c) or when an Asset's settings are updated against the
    union of assigned Capabilities' schemas (5g-c).

This module hoists the shared bits. Each BC keeps its own typed
error class (Family/Method/Plan/Run/Asset specific) so HTTP
exception handlers stay aligned with their BC namespace; the error
class is passed in as a parameter. Mirrors the `json_schema_subset`
hoist precedent (each BC's wrapper ~10 lines instead of ~80).

## Pattern memo

The "schema-validated values" pattern has two halves:
  1. **Declarer aggregate** owns the optional schema (Family,
     Method). Schema mutations validate well-formedness.
  2. **Carrier aggregate** owns the values (Asset, Plan, Run).
     Values mutations validate against the declarer's schema.

Both halves use the same constrained JSON Schema subset
(`cora.shared.json_schema_subset`) and the same
`jsonschema-rs` Draft 2020-12 engine. The strict-by-default posture
is uniform across both halves: missing schema +
non-empty values → reject with operator-facing guidance.

See `[[project_schema_validated_values_pattern]]` for the full
family map and operator vocabulary mapping
(settings vs parameters preserved per industrial convention).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping
from typing import Any

import jsonschema_rs

from cora.shared.json_schema_subset import DRAFT_2020_12_URI, check_subset

ALLOWED_UNIT_SYSTEMS: frozenset[str] = frozenset({"udunits", "ucum", "qudt", "iec61360", "ucefact"})
"""Closed namespace allowlist for the `unit.system` annotation
(locked in [[project_units_design]]). Each value names a unit
vocabulary whose codes are interpreted opaque-within-namespace:

  - ``udunits``: beamline-neighborhood default (NeXus, netCDF, EPICS-
    adjacent). Day-one pilot fixtures use this.
  - ``ucum``: clinical / cross-domain (HL7 FHIR, openEHR).
  - ``qudt``: linked-data / semantic-web; codes are IRIs.
  - ``iec61360``: Industry-4.0 / AAS submodel; codes are IRDIs.
  - ``ucefact``: UN/CEFACT Common Code; schema.org `QuantitativeValue`.

Widening this set is a deliberate decision driven by a real consumer
appearing at a seam. Adding a system here does not buy automatic
conversion across namespaces; that lives in the adapter layer
(`unit_codec`, created at first-boundary trigger)."""


def validate_schema_declaration(
    schema: dict[str, Any],
    *,
    error_class: type[ValueError],
) -> None:
    """Validate that `schema` is a well-formed JSON Schema in CORA's
    constrained subset (declarer-side write-time check).

    Four failure modes, all raised as `error_class(reason)`:
      1. Missing or wrong `$schema` declaration
      2. Forbidden keyword used (per `json_schema_subset.check_subset`)
      3. `unit` annotation present but malformed (per
         `validate_unit_annotations`)
      4. jsonschema-rs rejects the schema as malformed (for example an
         invalid `pattern` regex)

    Returns None on success. Caller persists the schema as-is; runtime
    validation of values against it (5g-c / 6g-b / 6g-c) reuses
    `validate_values_against_schema` below.

    Used by 5g-a (Family.settings_schema) and 6g-a
    (Method.parameters_schema).
    """
    declared = schema.get("$schema")
    if declared != DRAFT_2020_12_URI:
        msg = (
            f"$schema must be exactly {DRAFT_2020_12_URI!r} "
            f"(got: {declared!r}); CORA locks Draft 2020-12"
        )
        raise error_class(msg)

    check_subset(schema, path="<root>", error_class=error_class)

    validate_unit_annotations(schema, path="<root>", error_class=error_class)

    try:
        jsonschema_rs.Draft202012Validator(schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs rejected the schema as malformed: {exc}"
        raise error_class(msg) from exc


def validate_unit_annotations(
    schema: Mapping[str, Any],
    *,
    path: str,
    error_class: type[ValueError],
) -> None:
    """Recursively validate any `unit` annotation in `schema` has the
    locked three-field shape (per [[project_units_design]]).

    For every property whose declaration contains a `unit` key, the
    value must be a dict with:

      - REQUIRED ``system: str`` in `ALLOWED_UNIT_SYSTEMS`
      - REQUIRED ``code: str`` (non-empty)
      - OPTIONAL ``label: str``
      - No other keys

    Called from `validate_schema_declaration` after `check_subset`
    succeeds, so the underlying keyword whitelist is already known
    good. Recursion mirrors `check_subset`: walk `properties.<name>`
    for nested object properties.

    Raises `error_class(reason)` on the first violation. Returns None
    when no `unit` annotations are present (the common case for
    non-numeric schemas).
    """
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return
    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            continue
        prop_path = f"{path}.properties.{prop_name}"
        if "unit" in prop_schema:
            _check_unit_annotation_shape(
                prop_schema["unit"],
                path=f"{prop_path}.unit",
                error_class=error_class,
            )
        validate_unit_annotations(prop_schema, path=prop_path, error_class=error_class)


_REQUIRED_UNIT_KEYS: frozenset[str] = frozenset({"system", "code"})
_OPTIONAL_UNIT_KEYS: frozenset[str] = frozenset({"label"})


def _check_unit_annotation_shape(
    annotation: Any,
    *,
    path: str,
    error_class: type[ValueError],
) -> None:
    if not isinstance(annotation, dict):
        msg = f"unit annotation at {path} must be a dict (got: {type(annotation).__name__})"
        raise error_class(msg)
    keys = set(annotation.keys())
    missing = _REQUIRED_UNIT_KEYS - keys
    if missing:
        msg = f"unit annotation at {path} missing required keys: {sorted(missing)}"
        raise error_class(msg)
    extra = keys - _REQUIRED_UNIT_KEYS - _OPTIONAL_UNIT_KEYS
    if extra:
        msg = (
            f"unit annotation at {path} has unknown keys: {sorted(extra)}; "
            f"allowed: {sorted(_REQUIRED_UNIT_KEYS | _OPTIONAL_UNIT_KEYS)}"
        )
        raise error_class(msg)
    system = annotation["system"]
    if not isinstance(system, str):
        msg = f"unit.system at {path} must be a string (got: {type(system).__name__})"
        raise error_class(msg)
    if system not in ALLOWED_UNIT_SYSTEMS:
        msg = (
            f"unit.system {system!r} at {path} is not in CORA's allowed "
            f"namespace list: {sorted(ALLOWED_UNIT_SYSTEMS)}"
        )
        raise error_class(msg)
    code = annotation["code"]
    if not isinstance(code, str) or not code:
        msg = f"unit.code at {path} must be a non-empty string"
        raise error_class(msg)
    if "label" in annotation:
        label = annotation["label"]
        if not isinstance(label, str):
            msg = f"unit.label at {path} must be a string (got: {type(label).__name__})"
            raise error_class(msg)


def validate_values_against_schema(
    values: Mapping[str, Any],
    schema: dict[str, Any] | None,
    *,
    error_class: type[ValueError],
    no_schema_message: str | None = None,
) -> None:
    """Validate a values dict against a JSON Schema (carrier-side
    write-time check).

    Two postures, picked by whether `no_schema_message` is supplied:

      - **STRICT** (`no_schema_message` provided): schema=None +
        non-empty values rejects with the supplied message. Used by
        Plan.default_parameters and Run.effective_parameters at
        start_run. Forces operators to declare a schema before
        accepting overrides.
      - **RELAXED** (`no_schema_message=None`): schema=None always
        accepts (the caller has already decided schemaless is OK at
        this checkpoint). Used by adjust_run and future steering
        slices where the operator-trust posture is "operator started
        the Run; respect their steering judgement." Callers that pick
        this posture typically early-return on `schema is None` before
        calling, but passing `no_schema_message=None` makes the
        intent explicit and lets this helper own the dispatch.

    When `no_schema_message` is provided it MUST contain a `{keys}`
    placeholder; the function fills in a comma-separated list of
    the offending keys (sorted, single-quoted) before raising.

    Behavior:
      - schema is None AND values is empty → accept (trivially valid)
      - schema is None AND values is non-empty AND no_schema_message
        is None → accept (RELAXED posture)
      - schema is None AND values is non-empty AND no_schema_message
        is provided → raise error_class with no_schema_message.format(keys=...)
      - schema is non-None AND values is empty → accept (no
        required-field check at this layer; required applies at the
        per-aggregate consumer point — for example, effective_parameters
        at Run start, 6g-c)
      - schema is non-None AND values is non-empty → compile via
        jsonschema-rs Draft 2020-12, run iter_errors, raise on first
        violation with path-prefixed diagnostic

    The Asset.settings validator (5g-c) builds a UNION mega-schema
    from multiple Capabilities first, then could reuse the
    iter_errors path here (currently retains its own implementation
    because the multi-source pre-step is BC-specific).
    """
    if schema is None:
        if not values or no_schema_message is None:
            return
        keys = ", ".join(f"'{k}'" for k in sorted(values.keys()))
        raise error_class(no_schema_message.format(keys=keys))

    if not values:
        return

    try:
        validator = jsonschema_rs.Draft202012Validator(schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs failed to compile the schema: {exc}"
        raise error_class(msg) from exc

    errors = list(validator.iter_errors(dict(values)))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.instance_path) or "<root>"
        msg = f"validation failed at {path}: {first.message}"
        raise error_class(msg)


__all__ = [
    "ALLOWED_UNIT_SYSTEMS",
    "validate_schema_declaration",
    "validate_unit_annotations",
    "validate_values_against_schema",
]
