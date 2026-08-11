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


def render_row(row: "dict[str, object] | asyncpg.Record") -> dict[str, object]:
    """Render every column of one asyncpg `Record` (production) or plain
    `dict` (unit tests -- `Record` isn't constructible outside asyncpg's
    own protocol machinery)."""
    return {key: render_value(value) for key, value in row.items()}
