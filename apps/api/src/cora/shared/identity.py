"""Cross-BC identity NewType aliases for fact-act attribution.

Per [[project_fold_symmetry_design]], the Pass 1 fitness test detects
attribution fields by type rather than by name: a state field is
classified as an ATTRIBUTION field when its annotation is `ActorId`,
`ActorId | None`, `AgentId`, `AgentId | None`, or the trigger-aware
discriminated union `ActorId | MonitorSourceId | SchedulerTickId`.
Bare `UUID` annotations are skipped. Identity-ref cross-aggregate UUIDs
(Asset refs, Subject refs, Calibration target refs, and so on) carry
their own per-aggregate NewType in the same spirit and are skipped by
the same predicate. This shifts the discipline burden from
"exhaustively enumerate every attribution field name" to "always use
the right NewType at the annotation site", which is what makes the
fold-symmetry detection robust.

Four NewType aliases ship in this module:

  - `ActorId` -- a UUID that identifies a principal in Access BC's
                 Actor stream (humans, agents, service accounts).
                 Folded onto state by the `<verb>_by` attribution
                 field whenever the act was performed by an Actor.
  - `AgentId` -- a UUID that identifies an autonomous agent in Agent
                 BC's Agent stream. Per [[project_agent_bc_design]],
                 every Agent shares its `id` with the co-registered
                 Actor (`AgentId == ActorId` value-wise), but the
                 typing distinction lets a slice that explicitly
                 wants an Agent (not any Actor) reject bare Actor
                 inputs at type-check time.
  - `MonitorSourceId` -- a UUID that identifies a Monitor-driven
                 transition source (substream observation, EPICS PV,
                 file watcher). Appears in Supply's trigger-aware
                 union when no human performed the act.
  - `SchedulerTickId` -- a UUID that identifies an Auto-driven
                 timer / scheduler tick. Appears in Supply's
                 trigger-aware union when an automated periodic
                 process performed the act.

NewType is preferred over `TypeAlias` because the wrapper is a true
distinct type at type-check time (pyright rejects `UUID -> ActorId`
without an explicit `ActorId(uuid)` call) while remaining a zero-cost
identity function at runtime (no boxing, no isinstance overhead). This
gives the fitness test a load-bearing structural signal without
imposing a runtime tax.

Per-slice migration order is documented in
[[project_fold_symmetry_design]]; this module is the Pre-work slice
that lands the aliases as a no-op (no existing field annotations
change in the same slice). The per-BC rename + add-missing-half
slices follow and re-annotate fields field-by-field.
"""

from typing import NewType
from uuid import UUID

ActorId = NewType("ActorId", UUID)
AgentId = NewType("AgentId", UUID)
MonitorSourceId = NewType("MonitorSourceId", UUID)
SchedulerTickId = NewType("SchedulerTickId", UUID)


__all__ = [
    "ActorId",
    "AgentId",
    "MonitorSourceId",
    "SchedulerTickId",
]
