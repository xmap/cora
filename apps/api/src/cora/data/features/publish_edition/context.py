"""Cross-aggregate context the `publish_edition` decider validates against.

`PublishEditionContext` is built by the publish handler from:

  - The freshly-minted `PersistentIdentifier` from `PersistentIdentifierMinter.mint`
  - The post-mint `content_hash` from re-serializing the artifact with
    the minted PID baked in

Both fields are captured at handler time so the decider stays pure
(per the non-determinism principle).
"""

from dataclasses import dataclass

from cora.shared.identifier import PersistentIdentifier


@dataclass(frozen=True)
class PublishEditionContext:
    """Captured publish-time inputs the decider reads from."""

    external_pid: PersistentIdentifier
    published_content_hash: str
