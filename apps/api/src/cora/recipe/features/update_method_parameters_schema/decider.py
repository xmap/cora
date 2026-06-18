"""Pure decider for the `UpdateMethodParametersSchema` command.

Mostly delegates to `validate_parameters_schema` for
well-formedness; the only domain-level guard is "Method must exist".
Schema can be updated in any lifecycle status (Defined / Versioned /
Deprecated) so no source-state check.

A cross-BC subset guard runs: when the Method has a `capability_id`
and the bound Capability has a `parameters_schema`,
the proposed Method.parameters_schema MUST be a subset of the
Capability's contract. Pinned per STRICT-by-default posture from
[[project_schema_validated_values_pattern]].

## Idempotency: no-op on unchanged

If the proposed parameters_schema is structurally equal to the
current one (including both being None), no event is emitted. This
avoids audit-log noise from operators re-submitting the same schema;
per-attestation re-emission is meaningful for content versioning
(see version_method's "strict-not-idempotent-with-exception"
rationale) but not for schema declarations, where the value IS the
audit trail and identical re-submission carries no new information.
Mirrors `update_family_settings_schema` (Equipment BC) decider stance.

Invariants:
  - State must not be None -> MethodNotFoundError
  - If Method.capability_id is set, the bound Capability stream
    must exist (handler skipped the load when it was missing)
    -> CapabilityNotFoundError
  - parameters_schema (if non-None) must be a valid in-subset
    JSON Schema -> InvalidMethodParametersSchemaError
  - parameters_schema (if non-None) on an ITERATIVE Method MUST declare
    a max_iter-shape or tol-shape stopping key (a top-level property in
    ITERATIVE_STOPPING_KEYS) -> InvalidMethodIterativeStoppingFieldError
  - parameters_schema (if non-None AND Method.capability_id is set
    AND the loaded Capability has a parameters_schema) MUST be a
    structural subset of Capability.parameters_schema ->
    MethodParametersNotSubsetError
  - If proposed == current, return [] (no event emitted)
"""

from datetime import datetime

from cora.recipe.aggregates.capability import Capability, CapabilityNotFoundError
from cora.recipe.aggregates.method import (
    ITERATIVE_STOPPING_KEYS,
    ExecutionPattern,
    InvalidMethodIterativeStoppingFieldError,
    Method,
    MethodNotFoundError,
    MethodParametersNotSubsetError,
    MethodParametersSchemaUpdated,
    validate_parameters_schema,
)
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)
from cora.shared.json_schema_subset import check_schema_is_subset


def decide(
    state: Method | None,
    command: UpdateMethodParametersSchema,
    *,
    capability: Capability | None = None,
    now: datetime,
) -> list[MethodParametersSchemaUpdated]:
    """Decide the events produced by updating a method's parameters_schema.

    `capability` is the loaded Capability state when
    `state.capability_id` is set (loaded by the handler via the
    cross-BC port). When None, the handler intentionally skipped the
    load (either because Method.capability_id is None, legacy
    fixture, OR because the Capability stream is missing, in which
    case CapabilityNotFoundError fires here). Subset check ONLY
    fires when both Method.parameters_schema AND Capability.parameters_schema
    are present; one-sided cases are unconstrained.
    """
    if state is None:
        raise MethodNotFoundError(command.method_id)

    # cross-BC integrity: Method points at a
    # capability_id but the Capability stream is missing — bubble up
    # CapabilityNotFoundError as 404.
    if state.capability_id is not None and capability is None:
        raise CapabilityNotFoundError(state.capability_id)

    if command.parameters_schema is not None:
        validate_parameters_schema(command.parameters_schema)
        # compute classification invariant (L4(a)): an ITERATIVE Method's
        # schema, once set, must declare a stopping budget or tolerance.
        # A freshly-defined ITERATIVE Method with no schema yet stays in a
        # transient unconstrained state; this fires only when a schema is
        # being set (command.parameters_schema is not None).
        if state.execution_pattern == ExecutionPattern.ITERATIVE:
            declared_properties = set(command.parameters_schema.get("properties", {}))
            if ITERATIVE_STOPPING_KEYS.isdisjoint(declared_properties):
                raise InvalidMethodIterativeStoppingFieldError(state.id, ITERATIVE_STOPPING_KEYS)
        # subset guard. Only when BOTH schemas are
        # present do we have something to compare; either side being
        # None means "no contract on that side".
        if (
            capability is not None
            and capability.parameters_schema is not None
            and state.capability_id is not None
        ):
            try:
                check_schema_is_subset(
                    command.parameters_schema,
                    capability.parameters_schema,
                    path="$",
                    error_class=ValueError,
                )
            except ValueError as exc:
                raise MethodParametersNotSubsetError(
                    state.id, state.capability_id, str(exc)
                ) from exc

    if command.parameters_schema == state.parameters_schema:
        return []
    return [
        MethodParametersSchemaUpdated(
            method_id=state.id,
            parameters_schema=command.parameters_schema,
            occurred_at=now,
        )
    ]
