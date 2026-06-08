"""Cross-Family validation for Asset.settings.

`validate_settings_against_families(settings, families)`:
union all assigned Capabilities' settings_schemas (5g-a) and validate
the proposed settings dict against the union via `jsonschema-rs`.
Raises `InvalidAssetSettingsError(reason)` on failure with a clear
diagnostic.

The companion RFC 7396 `merge_patch` helper originally lived in this
module (5g-c shipped both together). Post-6g cleanup hoisted it to
`cora.shared.json_merge_patch` once the third call site
landed (5g-c here + 6g-b Plan.default_parameters + 6g-c Run
effective_parameters resolution). New callers import directly from
the infrastructure module.

## Union semantics

For each currently-assigned Family with a non-None
`settings_schema`:
  - Every property name declared in any Family's `properties`
    is allowed.
  - For properties declared in MULTIPLE Capabilities, all
    constraints intersect via `allOf`-style semantics
    (`jsonschema-rs` handles this natively when given an
    `allOf` array): `minimum` takes the highest, `maximum` takes
    the lowest, `type` must agree across all declarations.

The implementation builds a single mega-schema with `allOf: [...]`
(one entry per Family with a schema) PLUS an
`additionalProperties: false` clause whenever ANY schemas exist.
Schemaless Capabilities are no-ops in the union: they contribute
nothing to the allowed-keys set.

## Why not reuse `validate_values_against_schema`

This validator's mega-schema construction is structurally different
from the single-schema path the shared
`cora.shared.json_schema_validation.validate_values_against_schema`
walks, and that difference is forced by a real JSON Schema pitfall:
`additionalProperties: false` only sees properties declared in the
SAME schema object — it CANNOT see properties declared in `allOf`
subschemas (per JSON Schema 2020-12 spec; see the upstream
discussion at json-schema/json-schema#116). Naively wrapping each
Family's schema in `allOf` and hoping `additionalProperties:
false` would close the union over all the subschemas' property names
silently rejects every key that isn't redeclared at the root.

The standard 2020-12 fix is the `unevaluatedProperties` keyword,
which DOES recognize properties declared in subschemas. CORA's
constrained subset deliberately forbids it (see
`cora.shared.json_schema_subset` — keeping the subset small
is a separate locked design decision).

So the Asset validator manually closes the union: collect declared
property names from each Family's `properties`, emit them as
`properties: {k: True for k in declared}` at the root, then add
`additionalProperties: false` at the root and the per-Family
constraints under `allOf`. This is the correct workaround for the
pitfall under the subset constraint. Sharing the iter_errors loop
with `validate_values_against_schema` would save ~5 lines but
muddle the union-construction logic that justifies the standalone
implementation.

## Strict-by-default modes

A Family with `settings_schema=None` does not contribute to the
union. Three modes follow:

  - **DECLARED**: at least one assigned Family declares a
    schema. The validator strictly rejects keys not declared by
    any of the declared schemas (`additionalProperties: false`),
    and validates declared keys against their union constraints.
    Schemaless Capabilities present alongside declared ones are
    no-ops; they do NOT widen the accepted-keys set.
  - **ALL-SCHEMALESS**: every assigned Family is schemaless
    (none declares a schema). Empty settings is trivially valid;
    non-empty settings is rejected with a clear "no Family
    declares a schema" message. Mirrors the NO-CAPABILITIES
    posture for consistency.
  - **NO-CAPABILITIES**: the Asset has zero assigned Capabilities.
    Empty settings is trivially valid; non-empty settings is
    rejected with "Asset has no assigned Capabilities to validate
    against".

Originally the **PERMISSIVE** mode existed: when at least one
Family was schemaless AND at least one declared a schema, the
union widened to accept unknown keys. An audit reversed this for
consistency with the strict-when-no-Method-schema posture:
silent typo prevention beats graceful degradation when both are
at stake. Operators wanting "this Family has no settings"
declare `settings_schema={}` explicitly. See
[[project_run_parameters_design]] §audit-correction for the
shared rationale.

## Error shape

`InvalidAssetSettingsError` carries a `reason` string with enough
detail for an operator to fix the patch:
  - "key 'energy' is not declared by any assigned Family's
    settings_schema" (orphan)
  - "value <X> for key 'energy' violates schema constraint
    <details>" (constraint violation)
  - "key 'temperature' has incompatible types across Capabilities
    (Family A: number, Family B: string)" (true conflict)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping, Sequence
from typing import Any

import jsonschema_rs

from cora.equipment.aggregates.asset.state import InvalidAssetSettingsError
from cora.equipment.aggregates.family.state import Family
from cora.shared.json_schema_subset import DRAFT_2020_12_URI


def validate_settings_against_families(
    settings: Mapping[str, Any],
    families: Sequence[Family],
) -> None:
    """Validate `settings` against the union of `families`'
    settings_schemas. Raises InvalidAssetSettingsError on failure.

    Returns None on success. Strict-by-default: non-empty
    settings without any declared
    settings_schema is rejected. See module docstring for the three
    modes (DECLARED / ALL-SCHEMALESS / NO-CAPABILITIES).
    """
    schemas = [c.settings_schema for c in families if c.settings_schema is not None]

    # Edge case: no assigned Capabilities and no settings -> trivially valid.
    if not families and not settings:
        return

    # Edge case: no assigned Capabilities but non-empty settings -> orphan.
    if not families and settings:
        keys = ", ".join(f"'{k}'" for k in sorted(settings.keys()))
        msg = f"key(s) {keys} cannot be set: Asset has no assigned Capabilities to validate against"
        raise InvalidAssetSettingsError(msg)

    # ALL-SCHEMALESS mode. If every assigned Family is schemaless,
    # no schema constrains the union. Empty settings is trivially
    # valid (no contract, no values, no conflict). Non-empty
    # settings rejects with a clear message (mirrors the
    # NO-CAPABILITIES posture and the "Method declares no schema"
    # rejection). Operators wanting a schemaless
    # Family that nonetheless permits settings declare
    # `settings_schema={}` explicitly on the Family — empty
    # schema means "no constraints, but the Family has been
    # inspected" and joins the union as a no-op constraint that
    # still allows declared keys from siblings.
    if not schemas:
        if not settings:
            return
        keys = ", ".join(f"'{k}'" for k in sorted(settings.keys()))
        msg = (
            f"key(s) {keys} cannot be set: every assigned Family is "
            f"schemaless (settings_schema=None). Declare a settings_schema "
            f"on at least one Family (an empty `{{}}` is valid for "
            f"Capabilities with no settings to constrain) or remove the keys."
        )
        raise InvalidAssetSettingsError(msg)

    # Detect true cross-Family type conflicts BEFORE running
    # jsonschema-rs (the validator's error messages are less
    # operator-friendly than naming the conflicting Capabilities
    # ourselves).
    _check_cross_capability_type_conflicts(families)

    # Build the mega-schema: allOf the per-Family schemas, plus
    # the strict-mode clause (every key not declared by any schema
    # is rejected). Schemaless Capabilities are no-ops here; they
    # don't widen the allowed-keys set (audit reversal).
    mega: dict[str, Any] = {
        "$schema": DRAFT_2020_12_URI,
        "type": "object",
    }
    mega["allOf"] = list(schemas)
    declared_keys = _collect_declared_property_names(schemas)
    mega["properties"] = {k: True for k in declared_keys}
    mega["additionalProperties"] = False

    try:
        validator = jsonschema_rs.Draft202012Validator(mega)
    except (jsonschema_rs.ValidationError, ValueError) as exc:  # pragma: no cover
        # Double-defense: per-Family schemas already validated cleanly upstream,
        # so a union compile-failure here would mean an Ajv-vs-jsonschema-rs divergence.
        msg = f"jsonschema-rs failed to compile the union schema: {exc}"
        raise InvalidAssetSettingsError(msg) from exc

    errors = list(validator.iter_errors(dict(settings)))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.instance_path) or "<root>"
        msg = f"settings validation failed at {path}: {first.message}"
        raise InvalidAssetSettingsError(msg)


def _collect_declared_property_names(schemas: Sequence[dict[str, Any]]) -> set[str]:
    """Return the set of property names declared by any schema's top-
    level `properties` dict. Used to drive strict-mode orphan
    rejection."""
    declared: set[str] = set()
    for schema in schemas:
        properties = schema.get("properties")
        if isinstance(properties, dict):
            declared.update(properties.keys())
    return declared


def _check_cross_capability_type_conflicts(families: Sequence[Family]) -> None:
    """Surface incompatible-type declarations across Capabilities
    BEFORE handing off to jsonschema-rs.

    Walks the top-level `properties` dicts of each Family with a
    schema, and for every property name appearing in more than one
    Family, asserts the declared `type` is identical. If types
    differ, raises InvalidAssetSettingsError naming both Capabilities
    and the offending key.

    This is the only kind of conflict that no value can satisfy
    under `allOf` semantics (constraint differences like minimum +
    minimum just intersect to the most restrictive).
    """
    # property_name -> list of (family_id, declared_type)
    type_by_key: dict[str, list[tuple[str, Any]]] = {}
    for cap in families:
        schema = cap.settings_schema
        if schema is None:
            continue
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            continue
        for prop_name, prop_schema in properties.items():  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(prop_schema, dict):  # pragma: no cover  # malformed-schema guard
                continue
            declared_type = prop_schema.get("type")
            if declared_type is None:  # pragma: no cover  # type-less prop, nothing to compare
                continue
            type_by_key.setdefault(prop_name, []).append((str(cap.id), declared_type))

    for prop_name, entries in type_by_key.items():
        types = {t for _, t in entries}
        if len(types) > 1:
            descriptions = "; ".join(f"Family {cid}: {t}" for cid, t in entries)
            msg = (
                f"key '{prop_name}' has incompatible types across "
                f"Capabilities ({descriptions}); no value can satisfy "
                f"the union"
            )
            raise InvalidAssetSettingsError(msg)


__all__ = ["validate_settings_against_families"]
