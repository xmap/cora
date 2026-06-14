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

from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotVersionError,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
    AssemblyVersioned,
    FamilyNotFoundForAssemblyError,
    InvalidParameterOverridesSchemaError,
    SubAssemblyContentHashMismatchError,
    SubAssemblyCycleError,
    SubAssemblyNestingTooDeepError,
    SubAssemblyNotFoundForAssemblyError,
    SubAssemblySlotNameConflictError,
    WireReferencesUnknownSlotError,
)
from cora.equipment.aggregates.assembly._content_hash import compute_assembly_content_hash
from cora.equipment.features.version_assembly.command import VersionAssembly
from cora.equipment.features.version_assembly.context import VersionAssemblyContext
from cora.shared.json_schema_validation import validate_schema_declaration

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
      - No required_sub_assemblies link may point at this Assembly's own id
        -> SubAssemblyCycleError.
      - Every required_sub_assemblies child must resolve to a defined Assembly
        -> SubAssemblyNotFoundForAssemblyError (sorted-first missing).
      - No required_sub_assemblies child may itself declare sub-assemblies
        (one composing level is supported, matching register_fixture)
        -> SubAssemblyNestingTooDeepError (sorted-first).
      - Each required_sub_assemblies link's pinned content_hash must match the
        child's current content_hash -> SubAssemblyContentHashMismatchError
        (sorted-first drift).
      - No required_sub_assemblies link slot_name may collide with a leaf slot
        or another link -> SubAssemblySlotNameConflictError.
      - No leaf slot_name may appear in more than one composed blueprint
        once the parent's and each child's leaf slots merge into the flat
        namespace register_fixture materializes
        -> SubAssemblySlotNameConflictError (sorted-first collision).
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

    for ref in command.required_sub_assemblies:
        if ref.sub_assembly_id == state.id:
            raise SubAssemblyCycleError(state.id)
    if context.sub_assembly_missing_ids:
        first_missing_sub = next(iter(sorted(context.sub_assembly_missing_ids, key=str)))
        raise SubAssemblyNotFoundForAssemblyError(first_missing_sub)
    if context.sub_assembly_too_deep_ids:
        first_too_deep = next(iter(sorted(context.sub_assembly_too_deep_ids, key=str)))
        raise SubAssemblyNestingTooDeepError(first_too_deep)
    if context.sub_assembly_hash_mismatches:
        sub_id, pinned, current = next(
            iter(sorted(context.sub_assembly_hash_mismatches, key=lambda m: str(m[0])))
        )
        raise SubAssemblyContentHashMismatchError(sub_id, pinned=pinned, current=current)

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

    # Front-stop the slot-name-namespace closure the same way the wire
    # closure is front-stopped: a link slot_name colliding with a leaf
    # slot (or another link) is caught here as a 400 rather than as a
    # load-time evolver fault from Assembly.__post_init__ on a written
    # (poisoned) stream.
    seen_sub_assembly_names: set[str] = set()
    for link in command.required_sub_assemblies:
        link_name = link.slot_name.value
        if link_name in slot_names:
            raise SubAssemblySlotNameConflictError(
                link_name, reason="already a required_slots slot_name"
            )
        if link_name in seen_sub_assembly_names:
            raise SubAssemblySlotNameConflictError(
                link_name, reason="duplicate sub-assembly slot_name"
            )
        seen_sub_assembly_names.add(link_name)

    # Cross-blueprint leaf-name collision: register_fixture merges the
    # parent's own leaf slots and every (leaf) child's leaf slots into
    # one flat namespace. Detect a clash here, where the operator can
    # still rename, rather than only at register_fixture. Computed in
    # resolve_sub_assembly_pins (it holds the loaded children).
    if context.sub_assembly_leaf_collisions:
        first_collision = next(iter(sorted(context.sub_assembly_leaf_collisions)))
        raise SubAssemblySlotNameConflictError(
            first_collision,
            reason="slot_name appears in more than one composed blueprint",
        )

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
        required_sub_assemblies=command.required_sub_assemblies,
    )

    return [
        AssemblyVersioned(
            assembly_id=state.id,
            name=name,
            presents_as_family_id=command.presents_as_family_id,
            required_slots=command.required_slots,
            required_wires=command.required_wires,
            required_sub_assemblies=command.required_sub_assemblies,
            parameter_overrides_schema=command.parameter_overrides_schema,
            drawing=command.drawing,
            version=command.version,
            content_hash=content_hash,
            previous_content_hash=state.content_hash,
            occurred_at=now,
        )
    ]
