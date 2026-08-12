"""F6 rendering: the one table for turning a raw row into export bytes-ready form.

Per `project_record_export_v3.md` F6: UUID to string, datetime to UTC
ISO-8601, bytes to hex. UTC normalization is measured, not stylistic:
the same instant at `-05:00` and `+00:00` hashes differently, and
Postgres returns `timestamptz` columns in the session's configured
offset while payload timestamps were already written as UTC strings.

This only has to touch the OUTER `events` / `entries_*` row columns
that asyncpg hands back as typed Python objects (`uuid.UUID`, tz-aware
`datetime`, `bytes`). It must NOT recurse into `payload` / `metadata`:
every `to_payload()` in the tree already converts UUID and datetime
fields to plain strings before the row is written (verified against
`_dispositions.py`, the Step 0 generated table, whose entries for all
six `*LogbookOpened` classes show `logbook_id` as a flat `token:uuid`
field rather than a nested one), and the asyncpg pool's jsonb codec
(`cora.infrastructure.postgres.pool`) decodes straight to `dict` / `str`
/ etc, never back to `UUID` or `datetime`. Rendering jsonb contents a
second time here would be a no-op at best and silently wrong if a future
payload ever carried a real (not pre-stringified) UUID or datetime.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress at module level, matching the other
# entries-table readers.


def render_value(value: object) -> object:
    """Render one column value for export.

    `UUID -> str`, `datetime -> UTC ISO-8601 str`, `bytes`-like -> hex
    `str`. Everything else (str, int, float, bool, None, and jsonb-decoded
    dict/list contents) passes through unchanged.
    """
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        # asyncpg returns `timestamptz` columns as timezone-aware in the
        # session's configured offset; astimezone(UTC) normalizes
        # regardless of what that offset was.
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return value.hex()
    return value


class UndecodedJsonColumnError(RuntimeError):
    """A jsonb column arrived as a `str`, so the connection lacks codecs.

    asyncpg returns jsonb as text unless the connection registers the
    codecs `cora.infrastructure.postgres.pool` installs. An export over
    such a connection is not merely degraded, it is wrong in a way that
    hides: every payload becomes one opaque string, the bundle is
    written, the manifest hashes it, and `verify_record_hash.py` reports
    OK, because the artifact is perfectly self-consistent about the
    wrong structure. Redaction is the only stage that would notice, and
    only by crashing on a `str` where it wanted a mapping.

    An exporter whose product is meant to be verifiable by a stranger
    cannot leave that to luck, so the shape is checked where rows enter
    rather than where they happen to break.
    """

    def __init__(self, column: str) -> None:
        super().__init__(
            f"column {column!r} arrived as a str, so this connection has no "
            "jsonb codec registered; build it through "
            "cora.infrastructure.postgres.pool.create_pool, or register the "
            "same codecs before exporting. Exporting now would hash a record "
            "whose payloads are strings."
        )
        self.column = column


# The jsonb columns an exported row can carry: `payload` and `metadata`
# on `events`, `payload` again on the activities entries table. Named
# rather than sniffed, because only these are known to be jsonb.
#
# The check reads a decoded `str` as proof of a missing codec, which
# holds because every one of these columns is written from a
# `to_payload()` returning a dict, so a correctly decoded value is
# always a mapping (or NULL). A jsonb column that legitimately held a
# bare JSON string would decode to `str` too and trip this; none does,
# and one arriving is a modelling change that should come here first.
_JSON_COLUMNS = ("payload", "metadata")


def render_row(row: "dict[str, object] | asyncpg.Record") -> dict[str, object]:
    """Render every column of one asyncpg `Record` (production) or plain
    `dict` (unit tests -- `Record` isn't constructible outside asyncpg's
    own protocol machinery).

    Refuses a jsonb column that arrived as a `str`. See
    `UndecodedJsonColumnError`.
    """
    rendered = {key: render_value(value) for key, value in row.items()}
    for column in _JSON_COLUMNS:
        if isinstance(rendered.get(column), str):
            raise UndecodedJsonColumnError(column)
    return rendered
