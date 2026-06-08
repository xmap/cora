"""Shared constrained JSON Schema subset checker.

CORA accepts a deliberately small subset of JSON Schema Draft 2020-12
for Family.settings_schema and Method.parameters_schema. Both surfaces
want the same forbidden-keyword posture (no $ref, oneOf, allOf,
conditionals, etc.), so the keyword whitelist and recursive subset
checker live here once and are wrapped per BC with the appropriate
domain error class.

Hoisted once the third use site landed (Family schema + Asset settings
union compilation + Method parameters schema). Mirrors the
`validate_bounded_text` hoist precedent.

## Constrained subset (locked in [[project_capability_settings_schema]])

Top-level + properties-level keys allowed: `$schema`, `type`,
`required`, `properties`, `enum`, `minimum`, `maximum`, `pattern`,
`unit`.
Forbidden everywhere: `$ref`, `oneOf`, `anyOf`, `allOf`, `not`,
conditionals (`if`/`then`/`else`/`dependentSchemas`),
`additionalProperties` / `unevaluatedProperties` / `prefixItems` /
`$dynamicRef`, anything else.

`unit` is a custom annotation keyword (locked in
[[project_units_design]]): when present on a numeric property its
value is a `{system, code, label?}` dict declaring the field's
measurement unit. The subset checker treats `unit` as opaque — it
does NOT recurse into the annotation's value. Shape validation
(namespace allowlist, required keys) is done separately by
`json_schema_validation.validate_unit_annotations` which runs after
`check_subset` succeeds.

When widening this set with a new RECURSIVE keyword (for example
`items` for arrays, `patternProperties` for prefix-keyed maps), you
MUST also extend `check_subset` to recurse into that keyword's
value(s). Forgetting to do so opens a hole: forbidden keywords
nested inside the new keyword would slip through.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any

DRAFT_2020_12_URI = "https://json-schema.org/draft/2020-12/schema"

ALLOWED_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "$schema",
        "type",
        "required",
        "properties",
        "enum",
        "minimum",
        "maximum",
        "pattern",
        "unit",
    }
)


def check_subset(
    node: dict[str, Any],
    *,
    path: str,
    error_class: type[ValueError],
) -> None:
    """Recursively assert that `node` only uses keys in the allowed subset.

    Raises `error_class(reason)` on the first violation, where `reason`
    is a descriptive string. Recurses into `properties.<name>` (each
    value is itself a schema). The caller's `error_class` is what gets
    surfaced to the HTTP layer, so each BC keeps its own typed error
    while sharing the structural check.
    """
    forbidden = set(node.keys()) - ALLOWED_SCHEMA_KEYS
    if forbidden:
        msg = (
            f"forbidden keyword(s) {sorted(forbidden)} at {path}; "
            f"CORA's subset allows only {sorted(ALLOWED_SCHEMA_KEYS)}"
        )
        raise error_class(msg)

    properties = node.get("properties")
    if properties is None:
        return
    if not isinstance(properties, dict):
        msg = f"properties at {path} must be a dict (got: {type(properties).__name__})"
        raise error_class(msg)

    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            msg = (
                f"properties.{prop_name} at {path} must be a schema dict "
                f"(got: {type(prop_schema).__name__})"
            )
            raise error_class(msg)
        # Properties-level schemas don't need their own $schema
        # declaration; only the root carries it. We allow $schema
        # everywhere (harmless at nested levels) to keep the recursion
        # API simple. Pinned at both 5g-a and 6g-a test suites.
        check_subset(prop_schema, path=f"{path}.properties.{prop_name}", error_class=error_class)


def check_schema_is_subset(
    inner: dict[str, Any],
    outer: dict[str, Any],
    *,
    path: str,
    error_class: type[ValueError],
) -> None:
    """Recursively assert `inner` is a STRICT subset of `outer`.

    Cross-schema subset relation used by Recipe's
    `Method.parameters_schema ⊆ Capability.parameters_schema` check
    at `update_method_parameters_schema` time. Same constrained
    subset (`ALLOWED_SCHEMA_KEYS`) on both sides; the check verifies
    the inner schema doesn't widen the outer's contract.

    Rules (v1 — conservative; matches CORA's STRICT-by-default
    posture per [[project_schema_validated_values_pattern]]):
      1. inner.type must equal outer.type when both are present.
         A Method whose parameter has a different type than its
         Capability declares is rejected (no widening).
      2. inner.properties (when both schemas declare them) must be
         a subset by KEY: every key in inner.properties must exist
         in outer.properties. Recurse into each shared property's
         schema.
      3. inner.required must be a subset of outer's declared
         property keys (Method can't require a property the
         Capability didn't even declare).
      4. inner.enum (when both present) must be a subset of outer.enum
         (narrowing OK; widening rejected).
      5. inner.minimum (when both present) must be >= outer.minimum
         (narrowing OK; widening rejected).
      6. inner.maximum (when both present) must be <= outer.maximum.
      7. inner.pattern (when both present) must exactly equal
         outer.pattern. Pattern subsumption is undecidable in
         general; require exact match as the conservative default.
      8. inner.unit (when both present) must exactly equal outer.unit.

    Tolerance: a key present in outer but absent in inner is
    always allowed (Method doesn't have to mention every property
    Capability declares — only `required`-on-Method propagates).

    Raises `error_class(reason)` on the first violation, where
    `reason` is a descriptive string with the offending `path`.
    """
    # 1. type equality
    outer_type = outer.get("type")
    inner_type = inner.get("type")
    if outer_type is not None and inner_type is not None and inner_type != outer_type:
        msg = (
            f"type mismatch at {path}: inner '{inner_type}' must equal outer "
            f"'{outer_type}' (no widening permitted)"
        )
        raise error_class(msg)

    # 2. properties subset by key + recurse
    outer_props = outer.get("properties") or {}
    inner_props = inner.get("properties") or {}
    if not isinstance(outer_props, dict) or not isinstance(inner_props, dict):
        # Malformed schemas are out of scope here; `check_subset` catches
        # them on each schema independently. Skip the relation check.
        return
    extra_props = set(inner_props.keys()) - set(outer_props.keys())
    if extra_props:
        msg = (
            f"inner declares properties {sorted(extra_props)} at {path}.properties "
            f"that outer does not — Method may not introduce parameters not in "
            f"the Capability's contract"
        )
        raise error_class(msg)
    for prop_name in inner_props:
        outer_prop = outer_props[prop_name]
        inner_prop = inner_props[prop_name]
        if isinstance(outer_prop, dict) and isinstance(inner_prop, dict):
            check_schema_is_subset(
                inner_prop,
                outer_prop,
                path=f"{path}.properties.{prop_name}",
                error_class=error_class,
            )

    # 3. required subset of outer's declared properties
    inner_required = inner.get("required") or []
    if isinstance(inner_required, list):
        unknown_required = set(inner_required) - set(outer_props.keys())
        if unknown_required:
            msg = (
                f"inner requires {sorted(unknown_required)} at {path}.required "
                f"but outer does not declare those properties"
            )
            raise error_class(msg)

    # 4. enum subset
    outer_enum = outer.get("enum")
    inner_enum = inner.get("enum")
    if (
        isinstance(outer_enum, list)
        and isinstance(inner_enum, list)
        and not set(_hashable(x) for x in inner_enum).issubset(
            set(_hashable(x) for x in outer_enum)
        )
    ):
        msg = (
            f"enum mismatch at {path}: inner enum {sorted(map(repr, inner_enum))} "
            f"must be a subset of outer enum {sorted(map(repr, outer_enum))}"
        )
        raise error_class(msg)

    # 5. minimum narrowing
    outer_min = outer.get("minimum")
    inner_min = inner.get("minimum")
    if (
        isinstance(outer_min, int | float)
        and isinstance(inner_min, int | float)
        and inner_min < outer_min
    ):
        msg = (
            f"minimum mismatch at {path}: inner minimum {inner_min} must be >= "
            f"outer minimum {outer_min}"
        )
        raise error_class(msg)

    # 6. maximum narrowing
    outer_max = outer.get("maximum")
    inner_max = inner.get("maximum")
    if (
        isinstance(outer_max, int | float)
        and isinstance(inner_max, int | float)
        and inner_max > outer_max
    ):
        msg = (
            f"maximum mismatch at {path}: inner maximum {inner_max} must be <= "
            f"outer maximum {outer_max}"
        )
        raise error_class(msg)

    # 7. pattern exact match
    outer_pattern = outer.get("pattern")
    inner_pattern = inner.get("pattern")
    if (
        isinstance(outer_pattern, str)
        and isinstance(inner_pattern, str)
        and inner_pattern != outer_pattern
    ):
        msg = (
            f"pattern mismatch at {path}: inner pattern {inner_pattern!r} must "
            f"exactly equal outer pattern {outer_pattern!r} (pattern subsumption "
            f"is undecidable; exact equality is the conservative default)"
        )
        raise error_class(msg)

    # 8. unit exact match (per [[project_units_design]])
    outer_unit = outer.get("unit")
    inner_unit = inner.get("unit")
    if outer_unit is not None and inner_unit is not None and inner_unit != outer_unit:
        msg = (
            f"unit mismatch at {path}: inner unit {inner_unit!r} must exactly "
            f"equal outer unit {outer_unit!r}"
        )
        raise error_class(msg)


def _hashable(x: Any) -> Any:
    """Make enum values hashable for set comparison. Lists/dicts become
    tuples of their items; everything else passes through."""
    if isinstance(x, list):
        return tuple(_hashable(v) for v in x)
    if isinstance(x, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in x.items()))
    return x


__all__ = [
    "ALLOWED_SCHEMA_KEYS",
    "DRAFT_2020_12_URI",
    "check_schema_is_subset",
    "check_subset",
]
