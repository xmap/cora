"""Pure decider for the `VersionClearanceTemplate` command.

Additive within Active per [[project_slice9_design]] L4: NO FSM transition.
The decider checks that the parent template lookup resolved, that the
parent belongs to the same facility as the child (L5), and that
`new_version == state.version + 1` (monotonic bump).

`now` and `versioned_by` are injected by the application handler from
the Clock and Actor identity sources. `parent_lookup_result` is injected
by the handler after calling `ClearanceTemplateLookup.lookup`;
None signals the parent template id does not resolve to a projection
row.
"""

from datetime import datetime

from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotVersionError,
    ClearanceTemplateFacilityMismatchError,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateVersioned,
)
from cora.safety.features.version_clearance_template.command import (
    VersionClearanceTemplate,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId


def decide(
    state: ClearanceTemplate | None,
    command: VersionClearanceTemplate,
    *,
    now: datetime,
    versioned_by: ActorId,
    parent_lookup_result: ClearanceTemplateLookupResult | None,
) -> list[ClearanceTemplateVersioned]:
    """Decide the events produced by versioning an Active clearance template.

    Invariants:
      - State must not be None
        -> ClearanceTemplateNotFoundError(command.template_id)
      - supersedes_template_id must NOT equal template_id (no self-loop in
        the supersedes lineage)
        -> ClearanceTemplateCannotVersionError(state.id, state.status)
      - Current status must be Active
        -> ClearanceTemplateCannotVersionError(state.id, state.status)
      - parent_lookup_result must be non-None
        -> ClearanceTemplateNotFoundError(command.supersedes_template_id)
      - Parent's facility must match the child's facility
        -> ClearanceTemplateFacilityMismatchError(state.id, state.facility_code,
           FacilityCode(parent_lookup_result.facility_code))
      - new_version must equal state.version + 1
        -> ClearanceTemplateCannotVersionError(state.id, state.status)
    """
    if state is None:
        raise ClearanceTemplateNotFoundError(command.template_id)
    if command.supersedes_template_id == command.template_id:
        raise ClearanceTemplateCannotVersionError(state.id, state.status)
    if state.status != ClearanceTemplateStatus.ACTIVE:
        raise ClearanceTemplateCannotVersionError(state.id, state.status)
    if parent_lookup_result is None:
        raise ClearanceTemplateNotFoundError(command.supersedes_template_id)
    if parent_lookup_result.facility_code != state.facility_code.value:
        raise ClearanceTemplateFacilityMismatchError(
            state.id,
            state.facility_code,
            FacilityCode(parent_lookup_result.facility_code),
        )
    if command.new_version != state.version.value + 1:
        raise ClearanceTemplateCannotVersionError(state.id, state.status)

    return [
        ClearanceTemplateVersioned(
            template_id=state.id,
            new_version=command.new_version,
            supersedes_template_id=command.supersedes_template_id,
            occurred_at=now,
            versioned_by=versioned_by,
        )
    ]
