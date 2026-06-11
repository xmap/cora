"""Equipment-BC-aggregate-shared relational-ref NewType aliases.

Mirrors `cora.federation.aggregates._value_types` (CredentialId,
FacilityId). Equipment's first entry is `RoleId`, the relational
reference between the new Role aggregate (Layer 3 of
[[project-role-aggregate-design]]) and downstream consumers
(Family.presents_as, Assembly.presents_as, RoleRequirement.role_kind,
Capability.suggested_roles). RoleId lives here, not at
`cora.shared.identity`, for the same reason CredentialId does: the
fold-symmetry fitness test consumes `cora.shared.identity` as its
attribution-NewType allowlist, and a relational-ref NewType placed
there would pollute the test's semantics (the test would demand a
paired `*_at` timestamp for every `*_by` field, which is wrong for a
ref that is not a who-claims-a-fact attribution).

NewType is preferred over `TypeAlias` because the wrapper is a true
distinct type at type-check time (pyright rejects `UUID -> RoleId`
without an explicit `RoleId(uuid)` call) while remaining a zero-cost
identity function at runtime.

Future hoist trigger: when a second Equipment-BC relational-ref
NewType lands (rule-of-three relative to the Federation precedent's
2-entry seed; Equipment is at 1 today), the module name `_value_types`
already matches the established convention and no rename is needed.
"""

from typing import NewType
from uuid import UUID

RoleId = NewType("RoleId", UUID)


__all__ = [
    "RoleId",
]
