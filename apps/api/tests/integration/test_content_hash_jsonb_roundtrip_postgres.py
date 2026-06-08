"""PG-jsonb round-trip preserves content-hash equality.

The content-addressed identity design picked stdlib json sort-keys +
DSSE PAE wrap + SHA-256 specifically to avoid binding the hash to
Postgres jsonb internal bytes (which are version-unstable across PG
upgrades). But every event written through `EventStore` survives a
round-trip into `events.payload jsonb` and back into a Python dict.
This test pins the invariant the design relies on: that PG-jsonb's
normalization (dict-key reordering, whitespace stripping, number
normalization) preserves the canonical-hash equality class.

In other words: if `compute_content_hash(payload_type, body)` is `h`
before persistence, then `compute_content_hash(payload_type,
load_payload_from_jsonb(body))` is also `h`. Without this invariant,
a future PG upgrade or jsonb codec change would silently invalidate
historical content hashes pinned on Method / Plan /
CalibrationRevision / Trajectory VOs.

Coverage:
  - flat dict round-trip preserves hash
  - nested dict round-trips to identical hash even when PG reorders keys
  - frozenset (canonicalized to sorted list before encoding) round-trips
    identically regardless of original insertion order
  - Unicode (NFC strings) survives jsonb encoding without re-encoding
  - empty / null boundary values

Whitespace-sensitivity of the canonical pipeline itself is covered by
`tests/unit/infrastructure/test_canonicalization_whitespace.py` (no PG
needed: the canonical pipeline reduces to `json.loads` first, which
already strips whitespace).

The pool registers a `jsonb` codec (`encoder=json.dumps,
decoder=json.loads`); the canonical pipeline runs FIRST so any types
not directly JSON-serializable (frozenset, dataclass) are reduced
before the codec encoder sees them.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from typing import Any

import asyncpg
import pytest

from cora.shared.content_hash import canonical_body_bytes, compute_content_hash

_PAYLOAD_TYPE = "application/vnd.cora.method-versioned+json"


async def _roundtrip(pool: asyncpg.Pool, body: Any) -> Any:
    """Canonicalize `body`, store via the codec, read back as a Python value."""
    canonical = json.loads(canonical_body_bytes(body).decode("utf-8"))
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT $1::jsonb", canonical)


@pytest.mark.integration
async def test_pg_jsonb_roundtrip_preserves_content_hash_for_flat_dict(
    db_pool: asyncpg.Pool,
) -> None:
    body: dict[str, Any] = {"name": "XRF Fly Mapping", "version": 3, "active": True}
    original = compute_content_hash(_PAYLOAD_TYPE, body)
    roundtripped = await _roundtrip(db_pool, body)
    assert compute_content_hash(_PAYLOAD_TYPE, roundtripped) == original


@pytest.mark.integration
async def test_pg_jsonb_roundtrip_preserves_content_hash_for_nested_dict(
    db_pool: asyncpg.Pool,
) -> None:
    """PG jsonb is free to reorder dict keys internally; canonical-JSON
    re-sort on read recovers the original byte sequence."""
    body: dict[str, Any] = {
        "outer": {"z": 3, "a": 1, "m": {"y": "two", "x": "one"}},
        "list": [{"k": 2, "j": 1}, {"k": 4, "j": 3}],
    }
    original = compute_content_hash(_PAYLOAD_TYPE, body)
    roundtripped = await _roundtrip(db_pool, body)
    assert compute_content_hash(_PAYLOAD_TYPE, roundtripped) == original


@pytest.mark.integration
async def test_pg_jsonb_roundtrip_preserves_content_hash_for_unicode_nfc(
    db_pool: asyncpg.Pool,
) -> None:
    """PG jsonb stores UTF-8; an NFC string in must stay NFC out.
    A regression that emitted NFD (decomposed) form would shift the
    hash silently for any payload containing umlauts / accented chars."""
    body: dict[str, Any] = {"author": "Müller", "title": "Crystallography"}
    original = compute_content_hash(_PAYLOAD_TYPE, body)
    roundtripped = await _roundtrip(db_pool, body)
    assert roundtripped["author"] == "Müller"
    assert compute_content_hash(_PAYLOAD_TYPE, roundtripped) == original


@pytest.mark.integration
async def test_pg_jsonb_roundtrip_preserves_content_hash_across_frozenset_insertion_order(
    db_pool: asyncpg.Pool,
) -> None:
    """`frozenset` becomes a sorted list during canonicalization; the
    sorted list is what reaches PG. Two semantically-equivalent
    frozensets (different insertion order) must produce identical
    hashes after the round-trip, and must match the hash of the
    pre-roundtrip canonical form."""
    body_a: dict[str, Any] = {"tags": frozenset(["c", "a", "b"])}
    body_b: dict[str, Any] = {"tags": frozenset(["b", "c", "a"])}
    original = compute_content_hash(_PAYLOAD_TYPE, body_a)
    rt_a = await _roundtrip(db_pool, body_a)
    rt_b = await _roundtrip(db_pool, body_b)
    assert compute_content_hash(_PAYLOAD_TYPE, rt_a) == original
    assert compute_content_hash(_PAYLOAD_TYPE, rt_b) == original


@pytest.mark.integration
async def test_pg_jsonb_roundtrip_preserves_content_hash_for_empty_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """Empty-dict, empty-list, and null boundary cases: PG-jsonb
    preserves the structural shape; the hash matches the in-memory
    value."""
    body: dict[str, Any] = {"empty_dict": {}, "empty_list": [], "null": None}
    original = compute_content_hash(_PAYLOAD_TYPE, body)
    roundtripped = await _roundtrip(db_pool, body)
    assert compute_content_hash(_PAYLOAD_TYPE, roundtripped) == original
