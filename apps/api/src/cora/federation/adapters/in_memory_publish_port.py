"""In-memory PublishPort adapter for tests and dev fixtures.

Dict-backed, no sockets. Mirrors `InMemoryEventStore` shape. Test
entry verbs use a `simulate_*` naming convention so a test that
needs to exercise a publish-time failure can opt in without
plumbing a separate fake.

Production-tier substitute until the rule-of-two trigger fires
(see [[project_federation_port_design]] for the trigger criteria).
Wire-tier adapters land in a follow-up iteration with the matching
library pins.
"""

import contextlib
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.federation import (
    FederationCredentialRevokedError,
    PublishedArtifact,
    PublishReceipt,
)


class InMemoryPublishPort:
    """Dict-backed PublishPort with simulate_* test entry points.

    Construct empty, call `publish(artifact)` to record, call
    `published_artifacts()` to assert. Test entry verbs:

      - `simulate_credential_revoked(credential_id, revoked_at)`:
        next `publish` call raises `FederationCredentialRevokedError`
        when ANY credential id matches; clear with
        `clear_simulations()`.
    """

    def __init__(self, *, clock: object | None = None) -> None:
        self._published: list[PublishedArtifact] = []
        self._revoked_credentials: dict[UUID, datetime] = {}
        self._next_receipt_id = 0
        self._clock = clock

    async def publish(self, artifact: PublishedArtifact) -> PublishReceipt:
        for credential_id, revoked_at in self._revoked_credentials.items():
            raise FederationCredentialRevokedError(
                credential_id=credential_id, revoked_at=revoked_at
            )
        self._published.append(artifact)
        self._next_receipt_id += 1
        return PublishReceipt(
            receipt_bytes=f"in-memory-receipt-{self._next_receipt_id}".encode(),
            receipt_format_hint="in-memory/v1",
            transparency_log_hint="none",
            recorded_at=artifact.published_at,
        )

    def published_artifacts(self) -> tuple[PublishedArtifact, ...]:
        return tuple(self._published)

    def simulate_credential_revoked(self, credential_id: UUID, revoked_at: datetime) -> None:
        self._revoked_credentials[credential_id] = revoked_at

    def clear_simulations(self) -> None:
        self._revoked_credentials = {}

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            self._published.clear()
            self._revoked_credentials.clear()


__all__ = ["InMemoryPublishPort"]
