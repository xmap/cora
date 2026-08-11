"""Redact a whole `ExportedRecord`: the fail-closed switch plus both tiers.

Per `project_record_export_v3.md` F5's fail-closed switch: the exporter
refuses to produce a bundle marked publishable unless a redaction
profile is supplied and its hash matches. `redact_record` computes
`hash_redaction_profile()` itself and compares against the caller-
supplied `expected_redaction_profile_hash` BEFORE touching a single row,
so a stale or substituted disposition table aborts rather than silently
redacting under the wrong rules.
"""

from dataclasses import dataclass

from cora.infrastructure.record_export._export import ExportedRecord
from cora.infrastructure.record_export._hashing import hash_redaction_profile
from cora.infrastructure.record_export._redact_tier1 import Tier1Redactor, UnknownEventTypeError
from cora.infrastructure.record_export._redact_tier2 import (
    ensure_all_clearances_fired,
    redact_tier2_row,
)
from cora.infrastructure.record_export._tokens import TokenMap

__all__ = [
    "RedactedRecord",
    "RedactionProfileMismatchError",
    "RedactionResult",
    "UnknownEventTypeError",
    "redact_record",
]


class RedactionProfileMismatchError(RuntimeError):
    """`expected_redaction_profile_hash` does not match the disposition
    table this checkout would actually redact with.

    Refuses rather than redacting under an unverified or stale table:
    the exact failure mode the fail-closed switch exists to catch.
    """

    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            f"redaction profile mismatch: expected {expected!r}, this checkout's "
            f"disposition table hashes to {actual!r}. Refusing to redact."
        )
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True, slots=True)
class RedactedRecord:
    """The published projection of an `ExportedRecord`: same two-tier
    shape, every value passed through F5's dispositions."""

    streams: tuple[dict[str, object], ...]
    logbooks: dict[str, tuple[dict[str, object], ...]]


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """`redacted_record` is safe to hash as the published record.
    `token_map` is an artifact of THIS export, retained separately under
    H1's obligation; it must never be shipped or fed into anything
    hashed as the published record."""

    redacted_record: RedactedRecord
    token_map: TokenMap


def redact_record(
    record: ExportedRecord, *, expected_redaction_profile_hash: str
) -> RedactionResult:
    """Redact both tiers of `record` under one shared `TokenMap`.

    Raises `RedactionProfileMismatchError` before touching any row if
    the hash does not match; `UnknownEventTypeError` if a stream row's
    `event_type` has no entry in the disposition table at all;
    `UnfiredClearanceError` if a declared tier-2 jsonb clearance never
    matched a row in a kind present in this export.
    """
    actual_hash = hash_redaction_profile()
    if expected_redaction_profile_hash != actual_hash:
        raise RedactionProfileMismatchError(expected_redaction_profile_hash, actual_hash)

    token_map = TokenMap()

    tier1 = Tier1Redactor(token_map)
    redacted_streams = tuple(tier1.redact_row(row) for row in record.streams)

    fired_pointers: dict[tuple[str, str], set[str]] = {}
    redacted_logbooks = {
        kind: tuple(
            redact_tier2_row(kind, row, token_map=token_map, fired_pointers=fired_pointers)
            for row in rows
        )
        for kind, rows in record.logbooks.items()
    }
    ensure_all_clearances_fired(fired_pointers, kinds_present=frozenset(record.logbooks))

    return RedactionResult(
        redacted_record=RedactedRecord(streams=redacted_streams, logbooks=redacted_logbooks),
        token_map=token_map,
    )
