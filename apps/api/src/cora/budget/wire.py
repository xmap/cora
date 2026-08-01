"""Compose the budget BC's handlers from `Kernel`.

`wire_budget(deps)` is invoked once from the FastAPI lifespan and
the returned `BudgetHandlers` bundle is stored on `app.state.budget`.
Routes and MCP tools pull their handler out of that bundle. New
slices add a new field on `BudgetHandlers` and a single line in this
factory.

Cross-cutting decorators applied here mirror Campaign / Agent /
Supply / Safety / Caution:

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only) -- Idempotency-
     Key support. Wrapped before tracing so cache-hits and cache-
     misses both attribute to the tracing span.
  3. `with_tracing` -- OTel span around every handler call.

## Wired handlers

  - `grant_allocation`         (create-style; idempotency-wrapped)
  - `activate_allocation`      (transition; no idempotency wrap)
  - `update_allocation_ceiling` (update; no idempotency wrap)
  - `seal_allocation`          (transition; no idempotency wrap)
  - `void_allocation`          (transition; no idempotency wrap)

## TotalSpendReader

`seal_allocation.bind` takes the reader as an explicit keyword so
every wiring site states which ledger fold the seal snapshot records.
Production binds `make_ledger_total_spend(deps.spend_lookup)`, the
instance-total fold over `entries_decision_inferences` (the one-line
swap the `zero_total_spend` seam promised).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.budget.features import (
    activate_allocation,
    grant_allocation,
    seal_allocation,
    update_allocation_ceiling,
    void_allocation,
)
from cora.budget.features.seal_allocation import make_ledger_total_spend
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "budget"


@dataclass(frozen=True)
class BudgetHandlers:
    """The budget BC's handler bundle, each closed over Kernel."""

    grant_allocation: grant_allocation.IdempotentHandler
    activate_allocation: activate_allocation.Handler
    update_allocation_ceiling: update_allocation_ceiling.Handler
    seal_allocation: seal_allocation.Handler
    void_allocation: void_allocation.Handler


def wire_budget(deps: Kernel) -> BudgetHandlers:
    """Build the budget BC handlers from shared dependencies."""
    return BudgetHandlers(
        grant_allocation=with_tracing(
            with_idempotency(
                grant_allocation.bind(deps),
                deps.idempotency_store,
                command_name="GrantAllocation",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="GrantAllocation",
            bc=_BC,
        ),
        activate_allocation=with_tracing(
            activate_allocation.bind(deps),
            command_name="ActivateAllocation",
            bc=_BC,
        ),
        update_allocation_ceiling=with_tracing(
            update_allocation_ceiling.bind(deps),
            command_name="UpdateAllocationCeiling",
            bc=_BC,
        ),
        seal_allocation=with_tracing(
            seal_allocation.bind(
                deps, total_spend_reader=make_ledger_total_spend(deps.spend_lookup)
            ),
            command_name="SealAllocation",
            bc=_BC,
        ),
        void_allocation=with_tracing(
            void_allocation.bind(deps),
            command_name="VoidAllocation",
            bc=_BC,
        ),
    )
