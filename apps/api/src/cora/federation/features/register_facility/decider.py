"""Pure decider for the `RegisterFacility` command.

Pure function: given the (always None) Facility state, a
`RegisterFacility` command, and (post-Slice 6 Sub-Slice A) an
optional `parent_lookup_result` carrying the projection row for the
supplied `parent_id`, returns the events to append on the Facility
stream. No I/O, no awaits, no side effects.

`now`, `code`, `display_name`, and `registered_by` are constructed
by the application handler at the port edge (FacilityCode + FacilityName
VO construction enforces field-shape invariants and surfaces
`InvalidFacilityCodeError` + `InvalidFacilityNameError` at the route
boundary as 422). The decider receives already-validated VOs.

The Facility id is derived deterministically by the handler from
`FacilityCode.value` via `facility_stream_id` (UUID5 over a frozen
namespace); the decider receives the derived id and uses it verbatim
in the genesis event.

`parent_lookup_result` is the FacilityLookup projection row for the
supplied `parent_id`, OR `None` to signal "parent does not exist".
The handler issues the lookup at the port edge (capture, don't
recompute) and threads the result into the decider so it stays pure.
When `command.parent_id is None` the handler passes `None` here too
(the structural invariant Site-no-parent / Area-must-have-parent
checks below distinguish "parent_id absent" from "parent absent",
matching the locked field-vs-lookup discipline).

Invariants enforced by this decider (belt-and-braces with the Facility
dataclass `__post_init__`):
  - State must be None (genesis-only)
    -> FacilityAlreadyExistsError
  - kind=Site implies parent_id is None
    -> FacilitySiteCannotHaveParentError
  - kind=Area implies parent_id is non-None
    -> FacilityAreaMustHaveParentError
  - kind=Area + parent_id is non-None: parent_lookup_result must not
    be None (else `FacilityParentNotFoundError` at 404)
  - kind=Area + parent_id is non-None + parent_lookup_result is
    present: parent_lookup_result.kind must equal FacilityKind.SITE.value
    (else `FacilityAreaParentMustBeSiteError` at 422; closes the
    Slice 5 cross-stream deferral)

`code`, `display_name`, `kind`, and `alternate_identifiers` are
validated at the Pydantic + VO boundary (route / tool); the decider
trusts the typed inputs.
"""

from datetime import datetime

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityAlreadyExistsError,
    FacilityAreaMustHaveParentError,
    FacilityAreaParentMustBeSiteError,
    FacilityKind,
    FacilityParentNotFoundError,
    FacilityRegistered,
    FacilitySiteCannotHaveParentError,
)
from cora.federation.features.register_facility.command import RegisterFacility
from cora.infrastructure.ports import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId


def decide(
    state: Facility | None,
    command: RegisterFacility,
    *,
    now: datetime,
    facility_id: FacilityId,
    code: FacilityCode,
    registered_by: ActorId,
    parent_lookup_result: FacilityLookupResult | None = None,
) -> list[FacilityRegistered]:
    """Decide the events produced by registering a new Facility.

    Invariants:
      - State must be None (genesis-only) -> FacilityAlreadyExistsError
      - kind=Site + parent_id is not None -> FacilitySiteCannotHaveParentError
      - kind=Area + parent_id is None     -> FacilityAreaMustHaveParentError
      - kind=Area + parent_id is not None + parent_lookup_result is None
        -> FacilityParentNotFoundError
      - kind=Area + parent_lookup_result.kind != "Site"
        -> FacilityAreaParentMustBeSiteError
    """
    if state is not None:
        raise FacilityAlreadyExistsError(state.code)

    if command.kind is FacilityKind.SITE and command.parent_id is not None:
        raise FacilitySiteCannotHaveParentError(code, command.parent_id)

    if command.kind is FacilityKind.AREA and command.parent_id is None:
        raise FacilityAreaMustHaveParentError(code)

    if command.kind is FacilityKind.AREA and command.parent_id is not None:
        if parent_lookup_result is None:
            raise FacilityParentNotFoundError(code, command.parent_id)
        if parent_lookup_result.kind != FacilityKind.SITE.value:
            raise FacilityAreaParentMustBeSiteError(
                code,
                command.parent_id,
                parent_lookup_result.kind,
            )

    return [
        FacilityRegistered(
            facility_id=facility_id,
            code=code,
            display_name=command.display_name,
            kind=command.kind,
            parent_id=command.parent_id,
            registered_by=registered_by,
            occurred_at=now,
            alternate_identifiers=command.alternate_identifiers,
        )
    ]


__all__ = ["decide"]
