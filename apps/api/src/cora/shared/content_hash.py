"""SHA-256 content-addressed identity for CORA template aggregates.

Hoisted at design-lock time per `project_content_addressed_identity_design`
(2026-05-23). Used by:

  - Method / Plan / CalibrationRevision / Trajectory VO (per the
    design lock; per-aggregate implementation lands when each
    next-touch happens).
  - Candidate F signed events (`signing.py`): the `pae_bytes` output is
    the byte sequence the Ed25519 signer signs. Sharing one
    canonicalization profile across hashing and signing means one
    canonicalization audit, one test corpus, and one failure mode.

## Why this exact pipeline

The corpus survey (`project_canonicalization_research`) ruled out:

  - JCS via `rfc8785` library (1-year silence, bus-factor risk)
  - Binary canonicalization (CBOR / msgpack / protobuf): 10% win on a
    32-byte hash, not worth migration cost
  - Postgres jsonb internal bytes (version-unstable across PG)
  - Pydantic `model_dump_json()` directly (dict-key insertion order
    preserved, not canonical)

Locked: stdlib json sort-keys recipe + DSSE PAE wrap + SHA-256.

## The non-obvious safeguards

Three implementation details that are NOT obvious from the design lock
alone, surfaced by implementation research:

  1. NFC normalization MUST recurse into keys and values. The only
     defense against composed-vs-decomposed Unicode drift (Latin
     umlauts, Turkish dotless-i, Czech caron). Without it, a
     copy-paste between editors silently produces two distinct hashes
     for "the same" identifier.
  2. `set` and `frozenset` MUST be coerced to sorted lists before
     `json.dumps`, recursively. `sort_keys=True` sorts dict keys but
     does NOT sort list contents. A `frozenset[AssetPort]` field
     serialized through Pydantic + `json.dumps(sort_keys=True)` would
     produce a different hash on every Python process restart
     (PYTHONHASHSEED varies).
  3. DSSE PAE length is BYTE length, not character length. Use
     `len(s.encode("utf-8"))` for non-ASCII payload types, never
     `len(s)`. Most common DSSE port bug.

## What this helper does NOT do

  - Does NOT validate `payload_type` against a closed catalog. Callers
    pick from the documented scheme
    `application/vnd.cora.<event-type>+json`.
  - Does NOT handle Decimal or float fields. Per design lock anti-hook
    #8, hashed aggregates may not introduce these without revisiting
    the lock. `json.dumps` raises `TypeError` on Decimal and
    `ValueError` on NaN/Infinity (with `allow_nan=False`); failing
    loudly is the correct signal.
  - Does NOT sign anything. Signing is `cora.infrastructure.signing`
    layered on top.

## Stability across Python versions

Output stability depends on the Unicode Character Database version
shipped with the Python interpreter (UCD 15.1 in CPython 3.13, UCD 16.0
in 3.14). Upgrading the interpreter major version is a
historical-hash-recomputation event; pin Python via `uv` and treat
upgrades as a deliberate migration.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any


def _canonicalize(value: Any) -> Any:
    """Recursively normalize a value into a JSON-stable Python structure.

    Handles, in order:
      - str: NFC normalization
      - Pydantic BaseModel: `model_dump(mode="json")` then recurse
      - dataclass instance: `asdict` then recurse
      - Mapping: NFC-normalize keys, recurse values
      - set / frozenset: recurse into each element, then sort by
        canonical-JSON serialization of the element (sorts
        deterministically across sets-of-dicts, not only sets of
        primitives)
      - list / tuple: recurse
      - other (int / bool / None): pass through

    Unsupported types (Decimal, float NaN, bytes, datetime, UUID) flow
    through unchanged and trigger `TypeError`/`ValueError` from the
    eventual `json.dumps`. Per design lock anti-hook #8 this is the
    correct signal.
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _canonicalize(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return _canonicalize(asdict(value))
    if isinstance(value, Mapping):
        return {unicodedata.normalize("NFC", str(k)): _canonicalize(v) for k, v in value.items()}
    if isinstance(value, set | frozenset):
        canonicalized = [_canonicalize(item) for item in value]
        return sorted(
            canonicalized,
            key=lambda x: json.dumps(
                x,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
    if isinstance(value, list | tuple):
        return [_canonicalize(item) for item in value]
    return value


def canonical_body_bytes(body: Any) -> bytes:
    """Produce canonical UTF-8 JSON bytes for a payload.

    Pipeline: `_canonicalize` (NFC + set-to-sorted-list + dataclass /
    Pydantic dispatch, recursive) then `json.dumps` with `sort_keys=True`,
    compact separators, `ensure_ascii=False`, `allow_nan=False`. Output
    is the byte sequence wrapped by `pae_bytes` for hashing or signing.

    Raises `TypeError` on unsupported types (Decimal, bytes, datetime,
    UUID); `ValueError` on NaN/Infinity. Pydantic at the API boundary
    must convert datetime/UUID/Decimal to strings before payloads
    reach this helper. Per design lock these are the correct signals,
    not silent coercion.

    Pydantic `by_alias` is NOT applied: `model_dump(mode="json")` uses
    field names, not aliases. Callers that need by-alias hashing must
    dump the dict themselves before passing it in. The motivation is
    to keep the hash stable when an alias is added or removed without
    a schema-meaning change.

    `bool` and `int` alias inside Python sets (`True == 1` collapses
    set membership). The hash mirrors what the input actually contains
    after Python deduplicates; this is not a defect, it is set
    semantics. Aggregates whose hash-bearing fields care about the
    distinction must use lists, not sets.
    """
    canonical = _canonicalize(body)
    return json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def pae_bytes(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding.

    Format per `github.com/secure-systems-lab/dsse/blob/master/protocol.md`:
    `"DSSEv1" SP LEN(type) SP type SP LEN(body) SP body`.

    LEN is ASCII decimal, no leading zeros. LEN is BYTE length under
    UTF-8 encoding (matters for non-ASCII `payload_type`). Single 0x20
    separators. No trailing newline.

    Reference test vector from `securesystemslib/tests/test_dsse.py`:
        pae_bytes("http://example.com/HelloWorld", b"hello world")
        == b"DSSEv1 29 http://example.com/HelloWorld 11 hello world"
    """
    payload_type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 %d %b %d %b" % (
        len(payload_type_bytes),
        payload_type_bytes,
        len(body),
        body,
    )


def compute_content_hash(payload_type: str, body: Any) -> str:
    """Compute SHA-256 content hash for an event payload. 64-char lowercase hex.

    Full pipeline: `body` -> `canonical_body_bytes` -> `pae_bytes` ->
    `sha256.hexdigest()`. Stable across processes, across Python
    interpreter restarts within one major version, across hosts.

    `payload_type` follows the scheme
    `application/vnd.cora.<event-type>+json` per
    `project_content_addressed_identity_design`. The URI is bound into
    the hash via PAE so a `method-versioned` hash can never collide
    with a `plan-versioned` hash even when bodies happen to serialize
    identically. This helper does NOT validate the URI scheme; callers
    pick from the documented set.
    """
    body_bytes = canonical_body_bytes(body)
    pae = pae_bytes(payload_type, body_bytes)
    return hashlib.sha256(pae).hexdigest()


__all__ = [
    "canonical_body_bytes",
    "compute_content_hash",
    "pae_bytes",
]
