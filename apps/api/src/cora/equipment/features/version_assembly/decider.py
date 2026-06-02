"""Pure decider for the `VersionAssembly` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected. Same precedent as
version_method / version_family.

Re-attestation: same structural content produces the same
content_hash but emits a fresh AssemblyVersioned event so the
re-confirmation is captured in the audit log. Pinned by
`test_decide_allows_re_attestation_with_same_content`.
"""

from datetime import datetime

from cora.equipment.aggregates._assembly_content_hash import compute_assembly_content_hash
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotVersionError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    AssemblyVersioned,
    FamilyNotFoundForAssemblyError,
    InvalidParameterOverridesSchemaError,
    WireReferencesUnknownSlotError,
)
from cora.equipment.features.version_assembly.command import VersionAssembly
from cora.equipment.features.version_assembly.context import VersionAssemblyContext
from cora.infrastructure.json_schema_validation import validate_schema_declaration

_VERSIONABLE_STATUSES: tuple[AssemblyStatus, ...] = (
    AssemblyStatus.DEFINED,
    AssemblyStatus.VERSIONED,
)


def decide(
    state: Assembly | None,
    command: VersionAssembly,
    *,
    context: VersionAssemblyContext,
    now: datetime,
) -> list[AssemblyVersioned]:
    """Decide the events produced by versioning an existing Assembly.

    Invariants:
      - State must not be None -> AssemblyNotFoundError carrying the
        target assembly_id.
      - state.status must be in {Defined, Versioned}
        -> AssemblyCannotVersionError carrying the current status.
        Deprecated is terminal; new revisions must fork via
        define_assembly with a new id.
      - context.missing_family_ids must be empty
        -> FamilyNotFoundForAssemblyError carrying the sorted-first
        missing FamilyId for deterministic responses.
      - command.name must be valid -> InvalidAssemblyNameError
        (via AssemblyName VO).
      - Every wire endpoint must reference a slot in required_slots
        -> WireReferencesUnknownSlotError carrying the offending
        slot_name (defense-in-depth above the evolver-fold check).
      - command.parameter_overrides_schema, when non-None, must be a
        well-formed JSON Schema in CORA's constrained subset
        -> InvalidParameterOverridesSchemaError.
    """
    if state is None:
        raise AssemblyNotFoundError(command.assembly_id)
    if state.status not in _VERSIONABLE_STATUSES:
        raise AssemblyCannotVersionError(
            state.id,
            f"current status is {state.status.value}",
        )
    if context.missing_family_ids:
        first_missing = next(iter(sorted(context.missing_family_ids, key=str)))
        raise FamilyNotFoundForAssemblyError(first_missing)

    name = AssemblyName(command.name)

    # Defense-in-depth: closure-check the wires here so a bad command
    # surfaces at the API boundary as a 400 rather than as a load-time
    # evolver fault. Same check lives on `Assembly.__post_init__`.
    slot_names = {slot.slot_name.value for slot in command.required_slots}
    for wire in command.required_wires:
        if wire.source_slot_name not in slot_names:
            raise WireReferencesUnknownSlotError(wire.source_slot_name)
        if wire.target_slot_name not in slot_names:
            raise WireReferencesUnknownSlotError(wire.target_slot_name)

    if command.parameter_overrides_schema is not None:
        validate_schema_declaration(
            command.parameter_overrides_schema,
            error_class=InvalidParameterOverridesSchemaError,
        )

    content_hash = compute_assembly_content_hash(
        name=name,
        presents_as_family_id=command.presents_as_family_id,
        required_slots=command.required_slots,
        required_wires=command.required_wires,
        parameter_overrides_schema=command.parameter_overrides_schema,
    )

    return [
        AssemblyVersioned(
            assembly_id=state.id,
            name=name,
            presents_as_family_id=command.presents_as_family_id,
            required_slots=command.required_slots,
            required_wires=command.required_wires,
            parameter_overrides_schema=command.parameter_overrides_schema,
            drawing=command.drawing,
            version=command.version,
            content_hash=content_hash,
            previous_content_hash=state.content_hash,
            occurred_at=now,
        )
    ]
