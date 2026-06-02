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
  - `command.name` must be valid -> InvalidAssemblyNameError (via
    AssemblyName VO).
  - `command.parameter_overrides_schema`, when non-None, must be a
    well-formed JSON Schema in CORA's constrained subset
    -> InvalidParameterOverridesSchemaError (via shared declarer
    validator).

Structural VO invariants on `required_slots` / `required_wires`
(slot-name length, cardinality enum, non-empty required_families,
wire-port-name length, full-self-loop rejection) fire at VO
construction time in the route / tool layers, never inside the
decider. Internal closure (every wire endpoint references a declared
slot) is enforced by `Assembly.__post_init__` when the evolver folds
the AssemblyDefined event into state.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates._assembly_content_hash import compute_assembly_content_hash
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyAlreadyExistsError,
    AssemblyDefined,
    AssemblyName,
    FamilyNotFoundForAssemblyError,
    InvalidParameterOverridesSchemaError,
    WireReferencesUnknownSlotError,
)
from cora.equipment.features.define_assembly.command import DefineAssembly
from cora.equipment.features.define_assembly.context import DefineAssemblyContext
from cora.infrastructure.json_schema_validation import validate_schema_declaration


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
      - command.name must be valid -> InvalidAssemblyNameError
        (via AssemblyName VO).
      - Every wire endpoint must reference a slot in required_slots
        -> WireReferencesUnknownSlotError carrying the offending
        slot_name.
      - command.parameter_overrides_schema, when non-None, must be a
        well-formed JSON Schema in CORA's constrained subset
        -> InvalidParameterOverridesSchemaError.
    """
    if state is not None:
        raise AssemblyAlreadyExistsError(state.id)
    if context.missing_family_ids:
        first_missing = next(iter(sorted(context.missing_family_ids, key=str)))
        raise FamilyNotFoundForAssemblyError(first_missing)

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
        AssemblyDefined(
            assembly_id=new_id,
            name=name,
            presents_as_family_id=command.presents_as_family_id,
            required_slots=command.required_slots,
            required_wires=command.required_wires,
            parameter_overrides_schema=command.parameter_overrides_schema,
            drawing=command.drawing,
            version=command.version,
            content_hash=content_hash,
            occurred_at=now,
        )
    ]
