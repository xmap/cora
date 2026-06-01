"""Pure decider for the `VersionModel` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

Source-state guard uses tuple-membership (same precedent as
version_family and decommission_asset). The decider validates the
bounded-text VOs defensively (`ModelName`, `PartNumber`,
`ModelVersionTag`) so direct in-process callers get the same
protection as API-boundary callers. `declared_families` cardinality
is checked here (must be non-empty); the `Manufacturer` pairing
invariant is enforced by the `Manufacturer` dataclass itself before
the command reaches the decider (raises
`InvalidManufacturerIdentifierPairingError`).

The handler does NOT cross-BC-validate `declared_families` here:
per the design memo Lock, full-set re-validation at version time is
deferred to incremental `add_model_family` edits. `version_model`
accepts whatever `declared_families` the caller passes; downstream
slices catch stale family references at their own boundaries.

## Deliberate divergence from strict-not-idempotent

Most update-style transitions in the codebase are strict-not-
idempotent: re-mounting / re-activating / re-decommissioning raises.
version_model is the EXCEPTION (mirroring version_family). Calling
`version_model("v2")` twice in a row both succeed, producing two
`ModelVersioned` events with the same tag. This is intentional:
re-attestation is a legitimate audit moment ("the operator confirmed
v2 again on date X"), and the multi-source Versioned to Versioned
transition already permits the operation structurally. Tightening to
"must use a different tag" would couple the decider to history-
walking, which the eventual-consistency stance avoids.

Invariants:
  - State must not be None -> ModelNotFoundError
  - State.status must be in {Defined, Versioned}, i.e., not Deprecated
    -> ModelCannotVersionError(current_status=...)
  - declared_families must be non-empty -> InvalidDeclaredFamiliesError
  - Name must be valid -> InvalidModelNameError (via ModelName VO)
  - Part number must be valid -> InvalidPartNumberError
    (via PartNumber VO)
  - version_tag must be valid -> InvalidModelVersionTagError
    (via ModelVersionTag VO)
"""

from datetime import datetime

from cora.equipment.aggregates.model import (
    InvalidDeclaredFamiliesError,
    Model,
    ModelCannotVersionError,
    ModelName,
    ModelNotFoundError,
    ModelStatus,
    ModelVersioned,
    ModelVersionTag,
    PartNumber,
)
from cora.equipment.features.version_model.command import VersionModel

_VERSIONABLE_STATUSES: tuple[ModelStatus, ...] = (
    ModelStatus.DEFINED,
    ModelStatus.VERSIONED,
)


def decide(
    state: Model | None,
    command: VersionModel,
    *,
    now: datetime,
) -> list[ModelVersioned]:
    """Decide the events produced by versioning an existing model."""
    if state is None:
        raise ModelNotFoundError(command.model_id)
    if state.status not in _VERSIONABLE_STATUSES:
        raise ModelCannotVersionError(state.id, current_status=state.status)
    if not command.declared_families:
        raise InvalidDeclaredFamiliesError
    name = ModelName(command.name)
    part_number = PartNumber(command.part_number)
    version_tag = ModelVersionTag(command.version_tag)
    return [
        ModelVersioned(
            model_id=state.id,
            name=name.value,
            manufacturer=command.manufacturer,
            part_number=part_number.value,
            declared_families=command.declared_families,
            version_tag=version_tag.value,
            occurred_at=now,
        )
    ]
