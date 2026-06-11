"""The `UpdateCapabilitySuggestedRoles` command -- intent dataclass for 3E."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UpdateCapabilitySuggestedRoles:
    """Author the editorial `suggested_role_ids` set on a Capability.

    Per memo Lock 10 (documentation-only): the operator publishes the
    full new set; the evolver replaces wholesale. Bare frozenset[UUID]
    per cross-BC convention symmetric with RoleRequirement.role_kind.

    The handler edge-loads each role_id via `Kernel.role_lookup.lookup`
    (parallel `asyncio.gather` batch) so callers see
    `RoleNotFoundError` rather than a satisfaction-side mis-record.
    """

    capability_id: UUID
    suggested_role_ids: frozenset[UUID]
