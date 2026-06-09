"""Enclosure-BC-aggregate-shared NewType + bounded-text value objects.

Per [[project_enclosure_stage1_design]] L-state-5, BC-local relational-ref
NewTypes for the Enclosure BC live here rather than at
`cora.shared.identity`. Co-located with the aggregate kernel
(`cora.enclosure.aggregates.*`) because tach's BC-isolation rule
forbids `cora.enclosure.aggregates` from importing the BC top-level
`cora.enclosure`; co-locating the shared-types module inside the
aggregates namespace satisfies the rule while keeping the types
BC-local.

The infrastructure-tier identity module (`cora.shared.identity`) is
scoped to fact-act ATTRIBUTION NewTypes (`ActorId`, `AgentId`,
`MonitorSourceId`, `SchedulerTickId`) that the fold-symmetry fitness
test consumes as its allowlist. Co-locating relational-ref NewTypes
there would pollute that allowlist semantics: the fitness test would
treat such a field as an attribution field and demand a paired `*_at`
timestamp, which is wrong (it is a relational ref, not a
who-claims-a-fact). Federation BC's `_value_types.py` is the precedent
for this BC-local placement.

This module ships two symbols at this sub-slice:

  - `EnclosureId`: a UUID that identifies an Enclosure row in the
    Enclosure BC's Enclosure aggregate. Used internally for spine
    references.
  - `EnclosureReason`: a trimmed, bounded transition reason carried on
    `EnclosurePermitObserved` and `EnclosureDecommissioned` event
    payloads (1-500 chars). Mirrors `SupplyReason` shape exactly.

`EnclosureName` (the bounded display-name VO) is co-located with the
aggregate in `state.py` per the Supply / Facility precedent. The
`_value_types` module here is reserved for NewType id aliases and
the shared `EnclosureReason` VO that is consumed by event payloads
rather than the aggregate state.

`NewType` is preferred over `TypeAlias` because the wrapper is a true
distinct type at type-check time (pyright rejects `UUID -> EnclosureId`
without an explicit `EnclosureId(uuid)` call) while remaining a
zero-cost identity function at runtime.
"""

from dataclasses import dataclass
from typing import NewType
from uuid import UUID

from cora.shared.bounded_text import validate_bounded_text

EnclosureId = NewType("EnclosureId", UUID)


ENCLOSURE_REASON_MAX_LENGTH = 500


class InvalidEnclosureReasonError(ValueError):
    """The supplied transition reason is empty, whitespace-only, or too long.

    Validated at API boundary AND defensively at the decider so direct
    in-process callers (sagas, tests) get the same protection. Same
    precedent as `SupplyReason`, `RunAbortReason`, `PromotionReason`.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Enclosure transition reason must be 1-{ENCLOSURE_REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


@dataclass(frozen=True)
class EnclosureReason:
    """Free-form transition reason. Trimmed; 1-500 chars.

    Required on `EnclosurePermitObserved` and `EnclosureDecommissioned`
    event payloads. Same shape as `SupplyReason`, `RunAbortReason`,
    `PromotionReason`. Free-form by design; structured taxonomies are
    deferred-with-trigger watch items.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=ENCLOSURE_REASON_MAX_LENGTH,
            error_class=InvalidEnclosureReasonError,
        )
        object.__setattr__(self, "value", trimmed)


__all__ = [
    "ENCLOSURE_REASON_MAX_LENGTH",
    "EnclosureId",
    "EnclosureReason",
    "InvalidEnclosureReasonError",
]
