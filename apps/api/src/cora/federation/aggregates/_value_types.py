"""Federation-BC-aggregate-shared relational-ref NewType aliases.

Per [[project_facility_aggregate_design]] L4 (amended), federation-BC
relational references between aggregates (Credential ids, Facility ids,
future Permit / Seal ids) live here rather than at
`cora.shared.identity`. Co-located with the aggregate kernel
(`cora.federation.aggregates.*`) because tach's BC-isolation rule
forbids `cora.federation.aggregates` from importing the BC top-level
`cora.federation`; co-locating the shared-types module inside the
aggregates namespace satisfies the rule while keeping the types
BC-local.

The infrastructure-tier identity module is scoped to fact-act ATTRIBUTION
NewTypes (`ActorId`, `AgentId`, `MonitorSourceId`, `SchedulerTickId`)
that the fold-symmetry fitness test consumes as its allowlist. Co-locating
relational-ref NewTypes there would pollute that allowlist semantics:
the fitness test would treat `trust_anchor_credential_ids: frozenset[CredentialId]`
as an attribution field and demand a paired `*_at` timestamp, which is
wrong (it is a relational ref, not a who-claims-a-fact).

NewType is preferred over `TypeAlias` because the wrapper is a true
distinct type at type-check time (pyright rejects `UUID -> CredentialId`
without an explicit `CredentialId(uuid)` call) while remaining a
zero-cost identity function at runtime.

Two NewType aliases ship today:

  - `FacilityId`: a UUID that identifies a Facility row in the
    Federation BC's Facility aggregate. Used internally for spine
    references; cross-BC and cross-deployment references use
    `FacilityCode` (per [[project_structural_scope_design]] two-tier
    identity contract).
  - `CredentialId`: a UUID that identifies a Credential row in the
    Federation BC's Credential aggregate. Used by Facility's
    `trust_anchor_credential_ids` frozenset and (post-slice-6) by
    Seal's `online_credential_id` / `offline_credential_id` fields
    once the existing bare-UUID typing migrates.

Future hoist trigger: when `PermitId` and `SealId` follow the same
NewType pattern (rule-of-three), the module name `_value_types` may
generalize to `_identity` or `_ids`; defer until that lands.
"""

from typing import NewType
from uuid import UUID

CredentialId = NewType("CredentialId", UUID)
FacilityId = NewType("FacilityId", UUID)


__all__ = [
    "CredentialId",
    "FacilityId",
]
