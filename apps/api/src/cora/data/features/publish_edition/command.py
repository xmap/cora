"""The `PublishEdition` command for the publish_edition slice.

Carries the Edition id only; the persistent-identifier authority +
scheme are wired via the `PersistentIdentifierMinter` adapter at the handler. The
operator does NOT supply the external_pid: per design L33, the PID
comes from the port only (otherwise a malicious operator could
publish citation packages that don't match cited bytes).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PublishEdition:
    """Publish a Sealed Edition: mint a PID, re-serialize, emit Published."""

    edition_id: UUID
