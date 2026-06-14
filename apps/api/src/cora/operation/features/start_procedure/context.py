"""Cross-aggregate context the `start_procedure` decider validates against.

`ProcedureStartContext` is built by the `start_procedure` handler
from `load_asset` calls (one per target Asset id) plus the Supply
satisfaction snapshot for Phase-of-Run Procedures before reaching the
pure decider. The decider treats the loaded entities as opaque domain
data and validates the start preconditions without performing any
I/O.

This is the third decider in the codebase that takes upstream
aggregate state as input (after Plan's `define_plan` and Run's
`start_run`). Per the canonical pattern documented in
CONTRIBUTING.md: handler pre-loads, decider receives an immutable
context dataclass, no I/O in the decider.

Slice-local module by design: only `start_procedure` uses it today.

## Field semantics

  - `assets`: dict keyed by asset_id, loaded from
    `procedure.target_asset_ids`. Decider rejects if any is
    Decommissioned (`ProcedurePlanAssetDecommissionedError`). Empty dict
    is valid (facility-envelope procedures, for example beam-mode
    change, have no target Assets).

  - `needed_supplies_satisfaction`: mapping keyed by `Supply.kind`,
    each entry the tuple of every non-Decommissioned Supply of that
    kind. Loaded by the handler for Phase-of-Run Procedures (when
    `state.parent_run_id is not None`) via
    `deps.supply_lookup.find_supplies_by_kind(parent.method.needed_supplies)`.
    Empty when the Procedure is standalone (no parent_run_id) or
    when the parent Run's Method has empty `needed_supplies`. The
    decider gates on at-least-one-AVAILABLE per kind in
    `needed_supplies_snapshot` per
    [[project_supply_preflight_gate_design]].

## Future-additive fields (deferred per project_operation_design)

  - `decision_approval` -- Decision BC integration; deferred until a
    real consumer surfaces.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

from cora.equipment.aggregates.asset import Asset
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult


@dataclass(frozen=True)
class ProcedureStartContext:
    """Snapshot of upstream aggregate state at Procedure-start time.

    `assets` is loaded from `procedure.target_asset_ids` (empty dict
    when target_asset_ids is the empty frozenset, valid for facility-
    envelope procedures).

    `needed_supplies_satisfaction` is non-empty only when the
    Procedure has `parent_run_id` set AND the parent Run's Method
    declares any `needed_supplies`. Standalone Procedures pass the
    Supply gate trivially (Capability-level needed_supplies is a
    Watch item per [[project_supply_preflight_gate_design]]).
    """

    assets: dict[UUID, Asset]
    needed_supplies_satisfaction: Mapping[str, tuple[SupplyLookupResult, ...]] = field(
        default_factory=lambda: cast("Mapping[str, tuple[SupplyLookupResult, ...]]", {})
    )
    referencing_enclosures: tuple[EnclosureLookupResult, ...] = ()
    """Every Active Enclosure that any of the Procedure's target Assets
    (or their ancestors) declares as its `located_in_enclosure_id`. The
    handler walks the Asset ancestor closure
    (`deps.asset_lookup.ancestors_of`), collects the distinct
    `located_in_enclosure_id` across those rows, and loads their permit
    status via `deps.enclosure_lookup.find_by_ids(enclosure_ids=...)`.

    Empty tuple is Permit-by-default per the EnclosureLookup port
    docstring: an Asset located in no Enclosure has no enclosure-
    permit gate, AND facility-envelope Procedures with empty
    `target_asset_ids` trivially pass. The decider partitions each
    row on `permit_status == "Permitted" AND lifecycle == "Active"`;
    failing rows raise the appropriate cross-BC enclosure error per
    [[project_enclosure_stage1_design]] L-pre-1 (always-derive-from-
    Asset-chain). Procedure does NOT carry a `needed_enclosure_permits`
    field; the located-in chain IS the declaration."""
