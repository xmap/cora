"""Pure decider for the `VersionPlan` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

## Deliberate divergence from strict-not-idempotent

Same as version_practice (Recipe 6d-2), version_method (Recipe 6b),
and version_family (Equipment 5f-2): re-versioning with the same
tag succeeds and emits a fresh event. Re-attestation is a legitimate
audit moment. Pinned by
`test_decide_allows_versioning_with_same_tag_for_re_attestation`.

## Content hash

Computed here per non-determinism principle: the decider captures
the SHA-256 of the canonical body bytes for `Plan.content_subset()`
and pins it in the emitted PlanVersioned event. Re-attesting the
same content yields the same hash (intended equivalence-detection
semantic, Bazel input/output split pattern). The subset shape lives
on the aggregate per [[project_content_addressed_identity_design]];
this slice just calls it and hashes.

Invariants:
  - State must not be None -> PlanNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidPlanVersionTagError
  - State.status must be in {Defined, Versioned}
    -> PlanCannotVersionError(current_status=...)

Note: this decider does NOT re-validate the bind-time invariants
(family superset, upstream-not-deprecated, no-decommissioned-
asset). Versioning a Plan is a label change on an existing binding,
not a re-bind. Re-validation against current upstream state is the
job of a future ongoing-satisfiability projection (gate-review Q3
deferred option iii').
"""

from datetime import datetime

from cora.infrastructure.signing import event_type_to_payload_type
from cora.recipe.aggregates.plan import (
    PLAN_VERSION_TAG_MAX_LENGTH,
    InvalidPlanVersionTagError,
    Plan,
    PlanCannotVersionError,
    PlanNotFoundError,
    PlanStatus,
    PlanVersioned,
)
from cora.recipe.features.version_plan.command import VersionPlan
from cora.shared.content_hash import compute_content_hash

_VERSIONABLE_STATUSES: tuple[PlanStatus, ...] = (
    PlanStatus.DEFINED,
    PlanStatus.VERSIONED,
)

_PLAN_VERSIONED_PAYLOAD_TYPE = event_type_to_payload_type("PlanVersioned")


def decide(
    state: Plan | None,
    command: VersionPlan,
    *,
    now: datetime,
) -> list[PlanVersioned]:
    """Decide the events produced by versioning an existing plan."""
    if state is None:
        raise PlanNotFoundError(command.plan_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > PLAN_VERSION_TAG_MAX_LENGTH:
        raise InvalidPlanVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise PlanCannotVersionError(state.id, current_status=state.status)
    content_hash = compute_content_hash(_PLAN_VERSIONED_PAYLOAD_TYPE, state.content_subset())
    return [
        PlanVersioned(
            plan_id=state.id,
            version_tag=trimmed,
            occurred_at=now,
            content_hash=content_hash,
        )
    ]
