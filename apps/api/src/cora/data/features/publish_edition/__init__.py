"""`publish_edition`: transitions a Sealed Edition to Published.

Mints a persistent identifier via `PersistentIdentifierMinter.mint`, re-serializes the
artifact with the minted PID baked in (yielding a new
`published_content_hash`), and emits `EditionPublished`. Set-once on
the aggregate: re-publish is rejected with `EditionCannotPublishError`.
"""

from cora.data.features.publish_edition.handler import Handler, bind
from cora.data.features.publish_edition.route import router

__all__ = ["Handler", "bind", "router"]
