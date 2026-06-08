"""Pure decider for the `VersionMethod` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

Source-state guard uses tuple-membership (same precedent as
decommission_asset / version_family). The decider validates
`version_tag` defensively via `InvalidMethodVersionTagError` so
direct in-process callers get the same protection as API-boundary
callers.

## Deliberate divergence from strict-not-idempotent

Same as `version_family` (Equipment 5f-2): re-versioning with
the same tag succeeds and emits a fresh event. Re-attestation is a
legitimate audit moment ("the operator confirmed v2 again on date
X"). Tightening would couple the decider to history-walking, which
the eventual-consistency stance avoids. Pinned by
`test_decide_allows_versioning_with_same_tag_for_re_attestation`.

## Content hash

Computed here per non-determinism principle: the decider captures
the SHA-256 of the canonical body bytes for `Method.content_subset()`
and pins it in the emitted MethodVersioned event. Re-attesting the
same content yields the same hash (intended equivalence-detection
semantic, Bazel input/output split pattern). The subset shape lives
on the aggregate per [[project_content_addressed_identity_design]];
this slice just calls it and hashes.

Invariants:
  - State must not be None -> MethodNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidMethodVersionTagError
  - State.status must be in {Defined, Versioned}
    -> MethodCannotVersionError(current_status=...)
"""

from datetime import datetime

from cora.infrastructure.signing import event_type_to_payload_type
from cora.recipe.aggregates.method import (
    METHOD_VERSION_TAG_MAX_LENGTH,
    InvalidMethodVersionTagError,
    Method,
    MethodCannotVersionError,
    MethodNotFoundError,
    MethodStatus,
    MethodVersioned,
)
from cora.recipe.features.version_method.command import VersionMethod
from cora.shared.content_hash import compute_content_hash

_VERSIONABLE_STATUSES: tuple[MethodStatus, ...] = (
    MethodStatus.DEFINED,
    MethodStatus.VERSIONED,
)

_METHOD_VERSIONED_PAYLOAD_TYPE = event_type_to_payload_type("MethodVersioned")


def decide(
    state: Method | None,
    command: VersionMethod,
    *,
    now: datetime,
) -> list[MethodVersioned]:
    """Decide the events produced by versioning an existing method."""
    if state is None:
        raise MethodNotFoundError(command.method_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > METHOD_VERSION_TAG_MAX_LENGTH:
        raise InvalidMethodVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise MethodCannotVersionError(state.id, current_status=state.status)
    content_hash = compute_content_hash(_METHOD_VERSIONED_PAYLOAD_TYPE, state.content_subset())
    return [
        MethodVersioned(
            method_id=state.id,
            version_tag=trimmed,
            occurred_at=now,
            content_hash=content_hash,
        )
    ]
