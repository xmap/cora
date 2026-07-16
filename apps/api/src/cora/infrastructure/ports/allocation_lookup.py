"""AllocationLookup port: which spending envelope is currently Active?

Consumed by the envelope arm of the budget gate stack: the coarse
post-hoc gate (`cora.agent._budget_gate.find_allocation_breach`), the
pre-estimate `BudgetSpendGuard`, and the budget BC's own
CampaignClosed sealer subscriber. All three ask the same one-row
question: "is an envelope Active right now, and what are its ceiling
and window start?" v1 models at most one Active envelope per
deployment (one CORA instance, one beamline), so the port has no
by-id or list surface; `find_active` IS the whole query shape.

## Convention

Same neutral-port shape as `SpendLookup` and `LanguageModelLookup`:
a consumer-shaped Protocol + frozen result VO + an opt-out test stub
here, with the production adapter shipped by the BC that owns the
fact (the budget BC's `PostgresAllocationLookup` over
`proj_budget_allocation_summary`). The port lives in infrastructure
because the consumers span BCs (agent gates, budget sealer) and the
kernel carries it as a cross-cutting field.

## Failure direction

The kernel default is `NoActiveAllocationLookup` (always None): no
envelope declared means no envelope constraint. Declaring and
activating an allocation is what arms the gate, the same opt-in
posture as every lookup in the family, so every existing test and
allocation-less deployment is unaffected. The at-most-one-Active
invariant is enforced best-effort at activate time (activate_allocation
refuses with AllocationAlreadyActiveError when another envelope is
already Active); on an
anomalous overlap the adapter answers with the newest-activated
envelope (documented on `find_active`), so the gate keys on the most
recent operator intent rather than refusing to answer.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AllocationLookupResult:
    """The deployment's currently Active spending envelope.

    `activated_at` is the spend-window start every instance-total
    ledger fold uses (`[activated_at, as_of)`); `campaign_id` is the
    optional Campaign binding the CampaignClosed sealer matches on.
    """

    allocation_id: UUID
    ceiling_usd: float
    activated_at: datetime
    campaign_id: UUID | None


class AllocationLookup(Protocol):
    """Cross-cutting port: resolve the deployment's single Active envelope."""

    async def find_active(self) -> AllocationLookupResult | None:
        """Return the Active allocation envelope, or None when none is Active.

        None disarms the envelope check entirely (no envelope, no
        constraint). Should more than one row ever be Active (the
        best-effort grant/activate guard lost a race), the newest
        `activated_at` wins, with `allocation_id` as a deterministic
        tiebreak: the most recently opened window is the operator's
        current intent, and a stable answer beats an arbitrary one.
        """
        ...


class NoActiveAllocationLookup:
    """Test-default stub: no envelope is ever Active.

    Mirrors `AlwaysZeroSpendLookup`'s role: tests and deployments
    that never declared an allocation get this from the kernel
    defaults, so the envelope check stays disarmed (the opt-in
    posture: activating an envelope is what arms the gate).
    """

    async def find_active(self) -> AllocationLookupResult | None:
        return None


__all__ = [
    "AllocationLookup",
    "AllocationLookupResult",
    "NoActiveAllocationLookup",
]
