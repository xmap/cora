"""ClearanceLookup port: cross-BC query for Safety BC's clearance projection.

Used by Run BC's `start_run` handler to gate Run.start
on the presence of an Active Safety Clearance whose bindings cover
the Run's scope `(run_id, subject_id, asset_ids)`. Future Procedure
BC's `start_procedure` is the next candidate consumer.

## Convention

This is the second cross-BC port (after `Authorize`): one
implementor (Safety BC ships `PostgresClearanceLookup` reading
`proj_safety_clearance_summary`), many consumers (Run today; possibly
Procedure / Operation later). Lives in `cora.infrastructure.ports`
per the existing pattern (`Authorize`, `EventStore`, `IdempotencyStore`,
`Clock`, `IdGenerator` all live here).

The port is shaped around the CONSUMER's need (the Run-start gate
needs "what clearances reference this Run / its Subject / its
Assets"), not around Safety BC's domain language. Adapters translate
the projection's columns to this shape.

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graça: cross-BC integration at
command time should go through a port that the consumer shapes,
with the implementor providing the adapter. Replicated read models
(here: `proj_safety_clearance_summary`) are the modern recommendation
over synchronous calls to the upstream aggregate, because the
projection is already a denormalized cross-stream view.

CORA's `Authorize` port follows the same shape: consumer-shaped
contract, single implementor (Trust BC), placed in infrastructure
for neutral access by every BC. ClearanceLookup matches that
precedent.

## ExternalRef-based coverage: deferred

Run gains `external_refs: frozenset[ExternalRef]` as an
additive field, but the ClearanceLookup query does NOT yet match
against ExternalBindings. The projection has no `external_refs`
column today; adding one needs a side-table or jsonb column. Defer
until a concrete consumer (for example, a proposal-issued
ExternalBinding-only Clearance) trips on the gap.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class ClearanceLookupResult:
    """Summary row from `proj_safety_clearance_summary` for the Run-start gate.

    Carries the minimal columns the start_run decider needs to
    decide pass/fail. Loaded by the handler via
    `ClearanceLookup.find_covering` and handed to the decider
    in `RunStartContext.referencing_clearances`.

    `status` is the StrEnum value as a plain string (matches the
    projection's `TEXT` column); the decider treats it opaquely and
    partitions on `"Active"`.
    """

    clearance_id: UUID
    status: str
    template_id: UUID
    template_code: str
    facility_code: str


class ClearanceLookup(Protocol):
    """Cross-BC port: query Safety's clearance projection from Run BC."""

    async def find_covering(
        self,
        *,
        run_id: UUID,
        subject_id: UUID | None,
        asset_ids: frozenset[UUID],
    ) -> list[ClearanceLookupResult]:
        """Return every clearance whose bindings cover the requested scope.

        "Covers" means:
          - `run_id` appears in the clearance's `run_binding_ids`, OR
          - `subject_id` (when non-None) appears in the clearance's
            `subject_binding_ids`, OR
          - any of `asset_ids` appears in the clearance's
            `asset_binding_ids`.

        ExternalBinding-based coverage is NOT matched (deferred per
        the module docstring). Procedure binding is not matched
        because a Run has no Procedure-id reference today.

        Returns clearances in EVERY status (Defined, Submitted,
        UnderReview, Approved, Active, Expired, Rejected, Superseded).
        The decider partitions on `status == "Active"` so it can
        distinguish "no clearance at all" (-> RunRequiresActive...)
        from "clearance exists but none Active" (-> Coverage...).

        Empty list means no clearance references this Run's scope at
        all.
        """
        ...


class AlwaysCoveredClearanceLookup:
    """Test-default stub: returns ONE synthetic Active clearance.

    Mirrors `AllowAllAuthorize`'s test-default role for `Authorize`:
    tests that don't care about clearance gating get this stub from
    `build_postgres_deps` defaults, so existing Run tests don't have
    to seed real clearances. Tests that exercise the gate explicitly
    override with the real adapter (`PostgresClearanceLookup`) and
    seed clearances via `register_clearance` + transition handlers.

    Contract drift vs the production adapter: the Protocol promises
    "clearances in EVERY status" so the decider can distinguish
    'no clearance at all' from 'clearance exists but none Active'.
    This stub returns exactly one Active row and elides the
    inactive-clearance distinction. Tests that depend on the
    `Coverage…` vs `RequiresActive…` discrimination MUST use the
    real `PostgresClearanceLookup` adapter, not this stub.
    """

    async def find_covering(
        self,
        *,
        run_id: UUID,
        subject_id: UUID | None,
        asset_ids: frozenset[UUID],
    ) -> list[ClearanceLookupResult]:
        _ = subject_id  # unused (synthetic clearance "covers" everything)
        _ = asset_ids  # unused
        _ = run_id  # unused (synthetic clearance binds opaquely)
        # Use a sentinel facility-code string; the value is never read
        # in any decider path (the stub exists for tests that don't
        # exercise the clearance-gate logic).
        return [
            ClearanceLookupResult(
                clearance_id=NIL_SENTINEL_ID,  # sentinel "test stub" id
                status="Active",
                template_id=NIL_SENTINEL_ID,
                template_code="test-stub",
                facility_code="test-stub",
            )
        ]
