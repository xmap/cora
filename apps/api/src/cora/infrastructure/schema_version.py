"""Refuse to serve a database whose shape this build does not expect.

Migrations are applied out of band (`make migrate-apply`), never by the
app: `apps/api/Dockerfile` says so, and forward-only migrations mean the
image carries no way back. That separation is right, and it leaves one
window open. Applying migrations and starting the process are two
independent acts, so nothing except sequencing keeps them in step, and a
restore breaks the sequence by construction: the database returns to the
shape it had when the backup was taken while the image stays current.

`scripts/restore_drill.py` already reads the applied version out of
Atlas's own bookkeeping to prove a restore brought the schema back with
the data. Its docstring is candid that the drill migrates before it backs
up, so it cannot construct the stale-schema case, and that the only guard
for that case is an operator remembering to run `make migrate-status`
afterwards. This module is that guard as a mechanism instead.

## Why refusing is the proportionate response

An event store is append-only at the role level
(`project_immutability_guarantee`), so events written against the wrong
schema are not rows to correct later, they are history. The failure is
also not reliably loud: a mismatch that DROPS a constraint added by a
later migration leaves every write succeeding and admits exactly the
records the constraint existed to reject. Crashing on a missing column is
the lucky outcome. Refusing to start converts both into a five-second
message.

## Direction decides the remedy, so it decides the message

Behind and ahead are not symmetric, and a check that only reported
"mismatch" would send an operator down the wrong path half the time.
Behind is fixed by applying migrations. Ahead cannot be fixed that way at
all, because forward-only means there is nothing to apply, so the only
move is to run the image that matches. Each case names its own remedy.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

import asyncpg

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

SchemaPosture = Literal["matched", "degraded"]
"""Whether the applied schema is the one this build expects.

`degraded` is only reachable through an explicit operator override and
means the process booted against a mismatched schema with writes
refused. There is no posture for "mismatched and writing"; that state is
what this module exists to prevent.
"""


@dataclass(frozen=True)
class SchemaCheck:
    """The outcome of a boot-time schema check.

    Carries both versions, not just the posture, because the degraded
    path needs them downstream: `ReadOnlyEventStore` names both sides in
    its refusal, and a caller who hits that refusal is usually not the
    operator who set the override.
    """

    posture: SchemaPosture
    applied: str
    expected: str


EXPECTED_SCHEMA_VERSION: Final = "20260713000000"
"""The newest migration this build was written against.

Hand-maintained, and deliberately not derived at runtime: the image does
not ship `infra/atlas/migrations` (see the Dockerfile), so there is
nothing on disk to read. `tests/architecture/test_schema_version_pin.py`
fails the build when this drifts from the newest tracked migration, which
puts the cost of forgetting on CI rather than on a beamline.
"""

_VERSION_PATTERN: Final = re.compile(r"^\d{14}$")
"""Atlas's `YYYYMMDDHHMMSS`. Fixed width is what makes the ordering
comparison below a plain string compare; the architecture test pins the
format so that stays true."""

_APPLIED_VERSION_QUERY: Final = (
    "SELECT coalesce(max(version), '') FROM atlas_schema_revisions.atlas_schema_revisions"
)


class SchemaVersionError(RuntimeError):
    """The database's shape is not the one this build expects.

    Subclasses carry the remedy. Callers catch this base: catching a
    subclass would silently stop covering a case when another is added.
    """


class SchemaAbsentError(SchemaVersionError):
    """No migrations have been applied at all."""

    def __init__(self, expected: str) -> None:
        super().__init__(
            f"This database has no schema. CORA needs migration {expected}.\n"
            f"\n"
            f"Nothing has been applied here yet, so this is a new database "
            f"rather than a mismatched one.\n"
            f"\n"
            f"To fix: make migrate-apply"
        )
        self.expected = expected


class SchemaBehindError(SchemaVersionError):
    """The database predates this build."""

    def __init__(self, applied: str, expected: str) -> None:
        super().__init__(
            f"CORA will not start: the database is older than this build.\n"
            f"\n"
            f"  database is at   {applied}\n"
            f"  this build needs {expected}\n"
            f"\n"
            f"This is the normal state after restoring a backup, because a "
            f"restore returns the schema to its shape on the day the backup "
            f"was taken while this image stays current.\n"
            f"\n"
            f"To fix: make migrate-apply"
        )
        self.applied = applied
        self.expected = expected


class SchemaAheadError(SchemaVersionError):
    """The database postdates this build, which migrating cannot fix."""

    def __init__(self, applied: str, expected: str) -> None:
        super().__init__(
            f"CORA will not start: the database is newer than this build.\n"
            f"\n"
            f"  database is at   {applied}\n"
            f"  this build needs {expected}\n"
            f"\n"
            f"Applying migrations will NOT fix this. CORA's migrations are "
            f"forward-only, so there is nothing to apply and no way back. "
            f"Something started an older image than the one this database "
            f"has been migrated for.\n"
            f"\n"
            f"To fix: run the image built for {applied} or later."
        )
        self.applied = applied
        self.expected = expected


async def read_applied_version(pool: asyncpg.Pool) -> str | None:
    """Return the newest applied migration, or None if none have been.

    None covers both shapes a never-migrated database takes: Atlas's
    schema absent entirely, and the table absent within it. Neither is an
    error here, because "brand new database" and "wrong database" want
    different words and the caller is the one that knows which it wants.

    Every other failure propagates. A pool that cannot answer this query
    cannot serve traffic either, and swallowing that into a None would
    report a connectivity outage as a fresh install.
    """
    try:
        applied: object = await pool.fetchval(_APPLIED_VERSION_QUERY)
    except (asyncpg.UndefinedTableError, asyncpg.InvalidSchemaNameError):
        return None
    return str(applied) if applied else None


def compare_versions(applied: str | None, expected: str) -> None:
    """Raise unless `applied` is the expected schema. Pure, so the unit
    tier can drive every branch without a database.

    Deliberately reports no step count. Counting how far behind a
    database is would need the full list of versions, which the image
    does not carry (it ships no migrations directory), and baking 160
    strings into source to earn one sentence is a poor trade. The two
    timestamps are legible on their own: an operator can see at a glance
    whether they restored last Tuesday or last quarter.
    """
    if applied is None:
        raise SchemaAbsentError(expected)
    if applied == expected:
        return
    if applied > expected:
        raise SchemaAheadError(applied, expected)
    raise SchemaBehindError(applied, expected)


async def verify_schema_version(
    pool: asyncpg.Pool,
    *,
    allow_mismatch: bool = False,
    expected: str = EXPECTED_SCHEMA_VERSION,
) -> SchemaCheck:
    """Check the applied schema and report the resulting posture.

    `allow_mismatch` downgrades a version mismatch from a refusal to a
    read-only boot, so a restored database can be inspected without
    risking the append-only history. It deliberately does NOT cover
    `SchemaAbsentError`: the override exists to read a database that has
    the wrong schema, and one with no schema has nothing to read. Letting
    it through would turn "I want to look at last week's data" into a
    process that boots against an empty database and reports it as fine.
    """
    applied = await read_applied_version(pool)
    try:
        compare_versions(applied, expected)
    except SchemaAbsentError:
        raise
    except SchemaVersionError:
        if not allow_mismatch:
            raise
        # `applied` is never None here: the None case raised
        # SchemaAbsentError above and re-raised past this arm.
        return SchemaCheck("degraded", applied=applied or "", expected=expected)
    return SchemaCheck("matched", applied=expected, expected=expected)


def parse_versions(migration_files: Sequence[Path]) -> tuple[str, ...]:
    """Version strings from migration filenames, in applied order.

    Shared by the architecture test that pins `EXPECTED_SCHEMA_VERSION`
    and by the test fixture that records what Atlas would have recorded,
    so the two cannot disagree about what a version is.
    """
    return tuple(sorted(path.name.split("_", 1)[0] for path in migration_files))


def is_well_formed(version: str) -> bool:
    """Whether a version is Atlas's fixed-width timestamp.

    Fixed width is load-bearing: `compare_versions` orders with a string
    compare, which is only correct while every version has the same
    number of digits.
    """
    return _VERSION_PATTERN.match(version) is not None


__all__ = [
    "EXPECTED_SCHEMA_VERSION",
    "SchemaAbsentError",
    "SchemaAheadError",
    "SchemaBehindError",
    "SchemaCheck",
    "SchemaPosture",
    "SchemaVersionError",
    "compare_versions",
    "is_well_formed",
    "parse_versions",
    "read_applied_version",
    "verify_schema_version",
]
