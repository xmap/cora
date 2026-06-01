"""Pure decider for the `DefineModel` command.

Pure function: given the current Model state (None for a fresh
stream) and a `DefineModel` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports. The handler is also responsible for
the cross-BC `family_lookup` validation (every element of
`command.declared_families` must resolve to a registered Family);
that lookup happens before the decider is called, since the decider
is pure and the Family lookup is impure.

The `version_tag` VO validation is performed here (defensively) when
the caller supplies one; an empty initial tag is rejected with
`InvalidModelVersionTagError` just like Family's version_tag.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.model import (
    InvalidDeclaredFamiliesError,
    Model,
    ModelAlreadyExistsError,
    ModelDefined,
    ModelName,
    ModelVersionTag,
    PartNumber,
)
from cora.equipment.features.define_model.command import DefineModel


def decide(
    state: Model | None,
    command: DefineModel,
    *,
    now: datetime,
    new_id: UUID,
) -> list[ModelDefined]:
    """Decide the events produced by defining a new model.

    Invariants:
      - State must be None (genesis-only) -> ModelAlreadyExistsError
      - declared_families must be non-empty -> InvalidDeclaredFamiliesError
      - Name must be valid -> InvalidModelNameError (via ModelName VO)
      - Part number must be valid -> InvalidPartNumberError
        (via PartNumber VO)
      - version_tag, if supplied, must be valid
        -> InvalidModelVersionTagError (via ModelVersionTag VO)

    The Manufacturer VO's own pairing invariant is enforced by the
    Manufacturer dataclass itself before the command reaches the
    decider (raises InvalidManufacturerIdentifierPairingError).
    """
    if state is not None:
        raise ModelAlreadyExistsError(state.id)
    if not command.declared_families:
        raise InvalidDeclaredFamiliesError
    name = ModelName(command.name)
    part_number = PartNumber(command.part_number)
    if command.version_tag is not None:
        # Validate but discard the VO; the event carries the raw str.
        ModelVersionTag(command.version_tag)
    return [
        ModelDefined(
            model_id=new_id,
            name=name.value,
            manufacturer=command.manufacturer,
            part_number=part_number.value,
            declared_families=command.declared_families,
            occurred_at=now,
            version_tag=command.version_tag,
        )
    ]
