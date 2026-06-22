"""CautionLookup port: cross-BC query for Caution BC's active-cautions projection.

Used by Run BC's `start_run` handler to surface
operator-authored cautions whose target references the Run's scope
`(asset_ids, procedure_ids)` as a snapshot on the `RunStarted` event
payload. The snapshot serves three purposes (per the Caution design
memo's read-side layered surface): (1) operator-facing warning panel,
(2) audit-trail proof that the caution was visible when the run
started, (3) ack-on-consumption pattern (EHS convergent C7) — the ack
lives on the consumption event, never per-operator on the Caution
aggregate.

## Convention

This is the third cross-BC port (after `Authorize` and
`ClearanceLookup`): one implementor (Caution BC ships
`PostgresCautionLookup` reading `proj_caution_summary`), many consumers
(Run today; possibly Procedure / Operation later). Lives in
`cora.infrastructure.ports` per the existing pattern (`Authorize`,
`ClearanceLookup`, `EventStore`, `IdempotencyStore`, `Clock`,
`IdGenerator` all live here).

The port is shaped around the CONSUMER's need (the Run-start banner
needs "what cautions reference this Run's Asset/Procedure scope"),
not around Caution BC's domain language. Adapters translate the
projection's columns to this shape.

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graça: cross-BC integration at
command time should go through a port that the consumer shapes,
with the implementor providing the adapter. Replicated read models
(here: `proj_caution_summary`) are the modern recommendation over
synchronous calls to the upstream aggregate, because the projection
is already a denormalized cross-stream view.

CORA's `Authorize` and `ClearanceLookup` ports follow the same
shape: consumer-shaped contract, single implementor BC, placed in
infrastructure for neutral access by every BC. CautionLookup
matches that precedent.

## Non-blocking by design

KEY DIFFERENCE from `ClearanceLookup`: the snapshot informs the
event payload but NEVER gates the decider. The Caution BC exists
exactly because operator-authored tribal-knowledge cautions are
WARN-at-consumption, not BLOCK-at-consumption (anti-pattern #5 in
the Caution design memo). Blocking authority belongs to Safety BC
Clearance; cautions only warn.

The `start_run` decider does NOT raise any error class based on
the contents of the returned list. The handler embeds each entry
into the `RunStarted.acknowledged_cautions` payload tuple and
proceeds with the rest of the validation chain regardless of
severity, count, or category.
"""

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

# Local Literal mirroring `CautionSeverity` string values. Defined here
# (not imported from `cora.caution.aggregates.caution`) because tach
# forbids `cora.infrastructure -> cora.caution.aggregates`: the
# infrastructure layer depends on nothing in the cora package. The
# typing wins (callers get a checked enum-shaped set; indexing the
# adapter's ordinal map raises KeyError instead of silently defaulting
# on an unknown string) are the same as a typed enum import.
type MinSeverity = Literal["Notice", "Caution", "Warning"]


@dataclass(frozen=True)
class CautionLookupResult:
    """Summary row from `proj_caution_summary` for the Run.start non-blocking banner.

    Carries the minimal columns the start_run handler embeds in the
    `RunStarted.acknowledged_cautions` payload tuple. Loaded by the
    handler via `CautionLookup.find_active_in_scope` and handed to
    the decider in `RunStartContext.active_cautions`.

    `severity` is the StrEnum value as a plain string (matches the
    projection's `TEXT` column); the lookup adapter applies the
    severity-threshold filter in SQL via `min_severity`.

    `text_excerpt` / `workaround_excerpt` are the first 200 chars of
    each (full text available via `GET /cautions/{id}` if the
    operator wants the rest). The cap keeps the event payload bounded
    even when many cautions reference the run's scope.
    """

    caution_id: UUID
    target_kind: str  # "Asset" | "Procedure"
    target_id: UUID
    category: str
    severity: str  # "Notice" | "Caution" | "Warning"
    text_excerpt: str
    workaround_excerpt: str


class CautionLookup(Protocol):
    """Cross-BC port: query Caution's active-cautions projection from Run BC."""

    async def find_active_in_scope(
        self,
        *,
        asset_ids: frozenset[UUID],
        procedure_ids: frozenset[UUID],
        min_severity: MinSeverity = "Caution",
    ) -> list[CautionLookupResult]:
        """Return every Active caution whose target is in the requested scope.

        "In scope" means:
          - `target_kind == "Asset"` AND `target_id` is in `asset_ids`, OR
          - `target_kind == "Procedure"` AND `target_id` is in `procedure_ids`.

        `min_severity` thresholds the result by ordinal compare
        (`Notice` < `Caution` < `Warning`). The default `"Caution"`
        silences Notice-severity cautions from the Run.start banner
        per the Caution design memo's read-side surface table;
        callers wanting the full set (operator-dashboard view, tests)
        pass `min_severity="Notice"` explicitly.

        Only Active, currently-in-effect cautions are considered.
        Superseded and Retired cautions never appear, and neither do
        Active cautions whose `expires_at` window has elapsed (a
        `NULL` window is indefinite and always in effect): the result
        is the set in force right now, not merely the set that is
        Active in the projection. Empty `asset_ids` and `procedure_ids`
        both yield an empty list (a Run with no Asset/Procedure scope
        can't surface any cautions).

        Per the Caution design memo (anti-pattern #5), the result is
        NEVER used to gate the decider — only to embed an audit
        snapshot in the `RunStarted` event payload.
        """
        ...

    async def find_retired_for_target(
        self,
        *,
        target_kind: str,
        target_id: UUID,
        category: str,
        authored_by: UUID,
    ) -> list[CautionLookupResult]:
        """Return Retired cautions for one (target, category, author).

        The CautionPromoter operator-retirement-memory guard (Lock 5): before
        auto-promoting a Notice-only CautionProposal, the promoter consults this
        to see whether a matching Notice it previously registered was
        deliberately Retired by an operator. A non-empty result means "respect
        the operator's retirement, do not re-create" -> PromotionDeferred.

        Matches on `target_kind` + `target_id` + `category` + `authored_by`.
        The promoter passes its own agent id as `authored_by`, since the only
        agent-authored Cautions are its own registrations (no agent retires a
        Caution today; retire/supersede are human commands). Only
        `status = 'Retired'` rows are returned; Active and Superseded never
        appear.
        """
        ...


class AlwaysQuietCautionLookup:
    """Test-default stub: returns `[]`.

    Mirrors `AllowAllAuthorize` / `AlwaysCoveredClearanceLookup`'s
    test-default role: tests that don't care about caution snapshot
    semantics get this stub from kernel-construction defaults, so
    existing Run tests don't have to seed cautions. Tests that
    exercise the snapshot explicitly override with the real adapter
    (`PostgresCautionLookup`) and seed cautions via `register_caution`.

    The "quiet" naming mirrors the design memo's "WARN-not-BLOCK"
    semantic (anti-pattern #5): the lookup is silent at the
    test-default level, and the production adapter only ever
    surfaces additional payload entries (never gates).
    """

    async def find_active_in_scope(
        self,
        *,
        asset_ids: frozenset[UUID],
        procedure_ids: frozenset[UUID],
        min_severity: MinSeverity = "Caution",
    ) -> list[CautionLookupResult]:
        _ = asset_ids  # unused (stub never surfaces any cautions)
        _ = procedure_ids  # unused
        _ = min_severity  # unused
        return []

    async def find_retired_for_target(
        self,
        *,
        target_kind: str,
        target_id: UUID,
        category: str,
        authored_by: UUID,
    ) -> list[CautionLookupResult]:
        _ = (target_kind, target_id, category, authored_by)  # unused (stub)
        return []
