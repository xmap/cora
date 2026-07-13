"""Budget bounded context.

Owns the Allocation aggregate: the spending envelope the deployment's
beamline receives and spends, the system-of-record half of the
facility LLM-budget arc. Design lock: [[project_allocation_design]].

  - `Allocation` aggregate: identity + USD ceiling + note +
    optional Campaign binding + 4-state FSM
    `Granted -> Active -> Sealed`, with `Voided` from Granted/Active.

Balance is never stored: it folds from the inference ledger every
other spend tier sums. The allocation's own lifecycle IS the award
window (`activated_at` to `sealed_at`); the gate stack's envelope
check reads the Active envelope's ceiling against the
instance-total ledger fold over that window.

Lifecycle slices: `grant_allocation` (genesis -> Granted, dormant),
`activate_allocation` (Granted -> Active; opens the spend window),
`amend_allocation_ceiling` (Granted | Active; PUT semantics, the
cost-overrun tighten lever), `seal_allocation` (Active -> Sealed;
closing the books with a server-computed final-spend snapshot),
`void_allocation` (Granted | Active -> Voided; operator withdraws a
mistaken grant, REQUIRED reason).

Authz posture: every one of these five commands bounds the whole
instrument's LLM spend, so a real Trust policy should treat them as a
single instrument-admin tier, kept off the routine-operator grant.
`CloseCampaign` belongs in that tier too: the CampaignClosed sealer
seals the bound envelope, and a sealed envelope no longer constrains
spend, so authority to close a campaign transitively lifts the
ceiling. Under the default `AllowAllAuthorize` posture all of these
are open, the pre-existing deployment default, not new here.

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command + decider + handler + route + tool
    adapters/                 -- PostgresAllocationLookup (the AllocationLookup port)
    projections/              -- AllocationSummaryProjection (read model writer)
    subscribers/              -- AllocationSealerSubscriber (CampaignClosed -> seal)
    wire.py                   -- BudgetHandlers bundle + wire_budget(deps)
    routes.py                 -- register_budget_routes(app)
    tools.py                  -- register_budget_tools(mcp, get_handlers=...)
"""

from cora.budget._projections import register_budget_projections
from cora.budget._subscribers import register_budget_subscribers
from cora.budget.errors import UnauthorizedError
from cora.budget.routes import register_budget_routes
from cora.budget.tools import register_budget_tools
from cora.budget.wire import BudgetHandlers, wire_budget

__all__ = [
    "BudgetHandlers",
    "UnauthorizedError",
    "register_budget_projections",
    "register_budget_routes",
    "register_budget_subscribers",
    "register_budget_tools",
    "wire_budget",
]
