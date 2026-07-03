-- Bookmark row for the authority_revocation_holder Reaction.
--
-- Unlike a Projection (whose bookmark row rides its `init_proj_*`
-- table migration), a Reaction has no `proj_*` table of its own, so its
-- projection_bookmarks row is seeded here. The row MUST exist before the
-- subscriber is registered on the live worker: the advance loop does
-- `read_bookmark(conn, subscriber.name)` which raises MissingBookmarkError
-- when the row is absent, so without this seed the kill-switch would wedge
-- its own advance loop and silently never fire.
--
-- Name matches AuthorityRevocationHolderSubscriber.name. Sentinel cursor
-- ('0'::xid8, 0) means the subscriber replays from the start of history on
-- first poll (correct: it should hold any run in flight at enable time).

INSERT INTO projection_bookmarks (name)
VALUES ('authority_revocation_holder')
ON CONFLICT DO NOTHING;
