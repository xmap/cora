"""Pure decider for the `DefineAssembly` command.

Pure function: given the current Assembly state (None for a fresh
stream), the loaded context (FamilyId existence checks), and the
command, returns the events to append. No I/O, no awaits, no side
effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Invariants

  - State must be None (genesis-only) -> AssemblyAlreadyExistsError
    via stream collision (essentially impossible with UUIDv7 ids;
    defensive guard).
  - `context.missing_family_ids` must be empty
    -> FamilyNotFoundForAssemblyError carrying the FIRST missing id.
  - `context.missing_role_ids` must be empty (every RoleId in
    `presents_as` resolves) -> RoleNotFoundError carrying the FIRST
    missing id.
  - `command.name` must be valid -> InvalidAssemblyNameError (via
    AssemblyName VO).
  - `command.parameter_overrides_schema`, when non-None, must be a
    well-formed JSON Schema in CORA's constrained subset
    -> InvalidParameterOverridesSchemaError (via shared declarer
    validator).

Structural VO invariants on `required_slots` / `required_wires`
(slot-name length, cardinality enum, non-empty required_family_ids,
wire-port-name length, full-self-loop rejection) fire at VO
construction time in the route / tool layers, never inside the
decider. Internal closure (every wire endpoint references a declared
slot) is enforced by `Assembly.__post_init__` when the evolver folds
the AssemblyDefined event into state.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyAlreadyExistsError,
    AssemblyDefined,
    AssemblyName,
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
from cora.equipment.aggregates.role import RoleNotFoundError
from cora.equipment.features.define_assembly.command import DefineAssembly
from cora.equipment.features.define_assembly.context import DefineAssemblyContext
from cora.shared.json_schema_validation import validate_schema_declaration


def decide(
    state: Assembly | None,
    command: DefineAssembly,
    *,
    context: DefineAssemblyContext,
    now: datetime,
    new_id: UUID,
) -> list[AssemblyDefined]:
    """Decide the events produced by defining a new Assembly.

    Invariants:
      - State must be None (genesis-only) -> AssemblyAlreadyExistsError
        via stream collision; carries the pre-existing assembly_id.
      - context.missing_family_ids must be empty
        -> FamilyNotFoundForAssemblyError carrying the sorted-first
        missing FamilyId for deterministic error responses.
      - context.missing_role_ids must be empty
        -> RoleNotFoundError carrying the sorted-first missing RoleId
        for deterministic error responses.
      - command.name must be valid -> InvalidAssemblyNameError
        (via AssemblyName VO).
      - Every wire endpoint must reference a slot in required_slots
        -> WireReferencesUnknownSlotError carrying the offending
        slot_name.
      - command.parameter_overrides_schema, when non-None, must be a
        well-formed JSON Schema in CORA's constrained subset
        -> InvalidParameterOverridesSchemaError.
      - No required_sub_assemblies link may point at this Assembly's own id
        -> SubAssemblyCycleError.
      - Every required_sub_assemblies child must resolve to a defined Assembly
        -> SubAssemblyNotFoundForAssemblyError (sorted-first missing).
      - No required_sub_assemblies child may itself declare sub-assemblies
        (one composing level is supported, and register_fixture refuses a
        deeper child, so authoring rejects it too: a defined Assembly stays
        instantiable) -> SubAssemblyNestingTooDeepError (sorted-first).
      - Each required_sub_assemblies link's pinned content_hash must match the
        child's current content_hash -> SubAssemblyContentHashMismatchError
        (sorted-first drift).
      - No required_sub_assemblies link slot_name may collide with a leaf slot
        or another link -> SubAssemblySlotNameConflictError.
      - No leaf slot_name may appear in more than one composed blueprint
        once the parent's leaf slots and each child's leaf slots merge into
        the flat namespace register_fixture materializes
        -> SubAssemblySlotNameConflictError (sorted-first collision).
    """
    if state is not None:
        raise AssemblyAlreadyExistsError(state.id)
    if context.missing_family_ids:
        first_missing = next(iter(sorted(context.missing_family_ids, key=str)))
        raise FamilyNotFoundForAssemblyError(first_missing)
    if context.missing_role_ids:
        first_missing_role = next(iter(sorted(context.missing_role_ids, key=str)))
        raise RoleNotFoundError(first_missing_role)

    for ref in command.required_sub_assemblies:
        if ref.sub_assembly_id == new_id:
            raise SubAssemblyCycleError(new_id)
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

    # Internal closure: every wire endpoint must reference a declared
    # slot. The same invariant lives on `Assembly.__post_init__` so
    # the evolver fold also rejects a corrupt event stream, but the
    # decider fires it first so a bad command surfaces at the API
    # boundary as a 400 rather than as a load-time evolver fault.
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
    # still rename, rather than only at the end of the install-then-
    # register choreography. Computed in resolve_sub_assembly_pins
    # (it holds the loaded children); the decider just raises.
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

    presents_as = frozenset(RoleId(r) for r in command.presents_as)
    content_hash = compute_assembly_content_hash(
        name=name,
        presents_as=presents_as,
        required_slots=command.required_slots,
        required_wires=command.required_wires,
        parameter_overrides_schema=command.parameter_overrides_schema,
        required_sub_assemblies=command.required_sub_assemblies,
    )

    return [
        AssemblyDefined(
            assembly_id=new_id,
            name=name,
            presents_as=presents_as,
            required_slots=command.required_slots,
            required_wires=command.required_wires,
            required_sub_assemblies=command.required_sub_assemblies,
            parameter_overrides_schema=command.parameter_overrides_schema,
            drawing=command.drawing,
            version=command.version,
            content_hash=content_hash,
            occurred_at=now,
        )
    ]
