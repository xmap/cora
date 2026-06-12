"""ClearanceTemplateLookup port: cross-aggregate query for Safety BC's ClearanceTemplate projection.

Used by cross-aggregate consumers that hold a `template_id` from the
wire and need to validate the parent ClearanceTemplate exists (and
inspect its facility binding, status, or version) before committing a
command. First consumer is the Safety BC's `version_clearance_template`
handler: it resolves `command.supersedes_template_id` to a
`ClearanceTemplateLookupResult` at the handler port edge and threads
the result into the decider as `parent_lookup_result` so the decider
can enforce Lock L5 of `project_slice9_design` (same-facility
parent-chain validation). Future consumers include the
`register_clearance` and `amend_clearance` handlers, when those gain
`template_id` bindings to bind a Clearance instance to its template.

## Convention

This is a cross-aggregate port (Safety BC ships the production
adapter `PostgresClearanceTemplateLookup` reading
`proj_safety_clearance_template_summary`; multiple Safety BC handlers
consume it). Lives in `cora.infrastructure.ports` per the existing
pattern (`Authorize`, `ClearanceLookup`, `CautionLookup`,
`SupplyLookup`, `SecretStore`, `CredentialLookup`, `FacilityLookup`,
`AssetLookup`).

The port is shaped around the CONSUMER's need: parent-chain validation
needs "does this template exist, what facility owns it, what is its
status + version" to enforce the same-facility chain invariant and
reject parents that are not Active (or stale-version) before commit.

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graca: cross-aggregate integration
at command time should go through a port that the consumer shapes,
with the implementor providing the adapter. The replicated read
model (`proj_safety_clearance_template_summary`) is the modern
recommendation over synchronous replay of the ClearanceTemplate
aggregate, because the projection is already a denormalized
cross-stream view + already covers the FSM status + version facet.

## No BC imports in the port

`status` is typed `str` (not Safety BC's `ClearanceTemplateStatus`
StrEnum) and `facility_code` is typed `str` (not Federation BC's
`FacilityCode` value object) so this port stays inside
`cora.infrastructure`'s `depends_on = []` tach contract. The values
match the StrEnum / VO string values; consumer deciders partition by
literal comparison and cast to typed enums / VOs at their boundary
if they need the discipline.

`id` is typed `UUID` (Safety BC's `ClearanceTemplate.id` is bare
UUID, not a NewType, so no cross-BC NewType to thread). Consumers
that care about the typed identity wrap at their BC boundary.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ClearanceTemplateLookupResult:
    """Summary row from `proj_safety_clearance_template_summary` for cross-aggregate checks.

    Carries the minimal columns cross-aggregate consumers need to
    validate parent-chain invariants before commit. Loaded by the
    handler via `ClearanceTemplateLookup.lookup` and handed to
    the decider in the slice's context object (mirrors
    `AssetLookupResult` shape).

    `status` is the `ClearanceTemplateStatus` StrEnum value as a
    plain string (matches the projection's `TEXT` column); the
    consumer decider partitions on the literals it cares about
    ("Draft", "Active", "Deprecated", "Withdrawn").

    `facility_code` is the `FacilityCode` value object's string
    representation (matches the projection's `TEXT` column); the
    consumer decider compares it to the binding aggregate's
    `facility_code` to enforce same-facility parent-chain (Lock L5).

    `code` is the operator-readable template code; useful for
    surfacing in cross-aggregate error messages that name the
    template operators recognize rather than a bare UUID.

    `version` is the integer template version; consumers enforcing
    "new_version == parent.version + 1" or other monotonicity rules
    read it here.
    """

    id: UUID
    facility_code: str
    code: str
    status: str
    version: int


class ClearanceTemplateLookup(Protocol):
    """Cross-aggregate port: query Safety's ClearanceTemplate projection by id."""

    async def lookup(self, template_id: UUID) -> ClearanceTemplateLookupResult | None:
        """Return the projection row for `template_id`, or None if not found.

        Returning None signals "no ClearanceTemplate with that id is
        visible in the projection". Callers (`version_clearance_template`
        parent validation today; future `register_clearance` and
        `amend_clearance` template bindings) translate None to the
        appropriate domain error at the decider boundary (per Lock L5,
        `version_clearance_template` raises
        `ClearanceTemplateNotFoundError`).

        Templates in EVERY status are returned (Draft, Active,
        Deprecated, Withdrawn); the decider partitions on `status`
        if it needs to distinguish "no template at all" from "template
        exists but not Active".
        """
        ...


__all__ = ["ClearanceTemplateLookup", "ClearanceTemplateLookupResult"]
