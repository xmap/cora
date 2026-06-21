"""Pure decider for the `PublishEdition` command.

## Firing order (per design memo L16)

  1. UnauthorizedError (handler pre-decider)
  2. EditionNotFoundError (handler load + fold)
  3. EditionCannotPublishError (status != Sealed)
  4. EditionPublishedWithoutContentHashError (defensive invariant)
  5. Handler PersistentIdentifierMinter.mint -> PersistentIdentifierMintError 502
  6. Handler re-serialize -> sha256 -> published_content_hash
  7. Decider emits EditionPublished
"""

from datetime import datetime

from cora.data.aggregates.edition import (
    Edition,
    EditionCannotPublishError,
    EditionPublished,
    EditionPublishedWithoutContentHashError,
    EditionStatus,
)
from cora.data.features.publish_edition.command import PublishEdition
from cora.data.features.publish_edition.context import PublishEditionContext
from cora.shared.identity import ActorId


def decide(
    state: Edition,
    command: PublishEdition,
    *,
    context: PublishEditionContext,
    now: datetime,
    published_by: ActorId,
) -> list[EditionPublished]:
    """Decide the events produced by publishing a Sealed Edition.

    `state` is non-None (handler raised EditionNotFoundError if it
    were). Firing order per the docstring header.

    Invariants:
      (Firing order per the module docstring header.)
      - state.status must be SEALED -> EditionCannotPublishError
      - state.content_hash must be set (defensive)
        -> EditionPublishedWithoutContentHashError
    """
    _ = command

    if state.status is not EditionStatus.SEALED:
        raise EditionCannotPublishError(edition_id=state.id, current_status=state.status)

    if state.content_hash is None:
        raise EditionPublishedWithoutContentHashError(edition_id=state.id)

    return [
        EditionPublished(
            edition_id=state.id,
            external_pid_scheme=context.external_pid.scheme.value,
            external_pid_value=context.external_pid.value,
            published_content_hash=context.published_content_hash,
            occurred_at=now,
            published_by=published_by,
        )
    ]
