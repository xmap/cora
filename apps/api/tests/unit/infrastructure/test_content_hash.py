"""Unit tests for `cora.shared.content_hash`.

Coverage:
  - PAE format conformance via the canonical DSSE test vector
  - Canonical body bytes: stable across input shape variations
    (dict-vs-dataclass, frozenset insertion order, NFD-vs-NFC strings,
    nested dict key reordering)
  - Hash output shape: 64-char lowercase hex
  - PayloadType binding: different payload_type produces different hash
    for identical body (PAE prevents cross-type collision)
  - Failure modes: NaN raises, Decimal raises, unsupported types raise
  - Idempotency: canonicalizing a canonicalized value is the identity

The canonical DSSE test vector is from
`secure-systems-lab/dsse/blob/master/protocol.md` and matches the
`securesystemslib` and `sigstore-python` reference implementations.
"""

import math
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

import pytest

from cora.shared.content_hash import (
    canonical_body_bytes,
    compute_content_hash,
    pae_bytes,
)

# ---------- PAE format (canonical DSSE test vector) ----------


@pytest.mark.unit
def test_pae_bytes_matches_canonical_dsse_vector() -> None:
    """Canonical vector from the DSSE protocol spec; pins wire format."""
    assert pae_bytes("http://example.com/HelloWorld", b"hello world") == (
        b"DSSEv1 29 http://example.com/HelloWorld 11 hello world"
    )


@pytest.mark.unit
def test_pae_bytes_uses_byte_length_not_char_length_for_non_ascii_type() -> None:
    """payload_type byte-length differs from char-length for multibyte UTF-8.
    The most common DSSE port bug is using `len(s)` instead of
    `len(s.encode("utf-8"))` for the length prefix."""
    payload_type = "application/vnd.cora.method-versioned+json"
    payload_type_with_umlaut = "application/vnd.cora.müthod-versioned+json"
    body = b""
    pae_ascii = pae_bytes(payload_type, body)
    pae_umlaut = pae_bytes(payload_type_with_umlaut, body)
    assert pae_ascii.startswith(b"DSSEv1 " + str(len(payload_type)).encode())
    # 'ü' is 2 bytes in UTF-8, so byte-length is char-length + 1
    assert pae_umlaut.startswith(b"DSSEv1 " + str(len(payload_type) + 1).encode())


@pytest.mark.unit
def test_pae_bytes_includes_body_byte_length_prefix() -> None:
    body = b"hello world"
    pae = pae_bytes("type", body)
    assert b" 11 hello world" in pae


# ---------- Hash output shape ----------


@pytest.mark.unit
def test_compute_content_hash_returns_64_char_lowercase_hex() -> None:
    h = compute_content_hash("application/vnd.cora.method-versioned+json", {})
    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


@pytest.mark.unit
def test_compute_content_hash_is_deterministic_across_calls() -> None:
    payload_type = "application/vnd.cora.method-versioned+json"
    body = {"name": "my method", "version": 1}
    assert compute_content_hash(payload_type, body) == compute_content_hash(payload_type, body)


# ---------- PayloadType binding (cross-type collision prevention) ----------


@pytest.mark.unit
def test_compute_content_hash_differs_for_different_payload_types() -> None:
    """Different payload_type produces different hash for identical body.
    Without PAE wrapping, two events with the same payload but
    different types would collide. PAE binds the type into the hash."""
    body = {"name": "x"}
    h_method = compute_content_hash("application/vnd.cora.method-versioned+json", body)
    h_plan = compute_content_hash("application/vnd.cora.plan-versioned+json", body)
    assert h_method != h_plan


# ---------- Canonical body bytes: stability across input shape ----------


@pytest.mark.unit
def test_canonical_body_bytes_stable_across_dict_insertion_order() -> None:
    a = {"x": 1, "y": 2, "z": 3}
    b = {"z": 3, "y": 2, "x": 1}
    assert canonical_body_bytes(a) == canonical_body_bytes(b)


@pytest.mark.unit
def test_canonical_body_bytes_stable_across_nested_dict_insertion_order() -> None:
    """Sort-keys must recurse into nested dicts.
    Pinned because `json.dumps(sort_keys=True)` does sort recursively,
    but a regression to a single-level sort would silently break."""
    a = {"outer": {"x": 1, "y": 2}}
    b = {"outer": {"y": 2, "x": 1}}
    assert canonical_body_bytes(a) == canonical_body_bytes(b)


@pytest.mark.unit
def test_canonical_body_bytes_stable_across_frozenset_insertion_order() -> None:
    """sort_keys=True sorts dict KEYS, not list contents.
    Without explicit set-to-sorted-list coercion, frozenset iteration
    order varies with PYTHONHASHSEED and the hash would be
    non-deterministic across processes."""
    a = frozenset(["c", "a", "b"])
    b = frozenset(["b", "c", "a"])
    assert canonical_body_bytes({"tags": a}) == canonical_body_bytes({"tags": b})


@pytest.mark.unit
def test_canonical_body_bytes_stable_for_frozenset_of_dataclasses() -> None:
    """Frozen dataclasses dispatched via asdict become dicts inside the set.
    `sorted` on a list of dicts would fail without our canonical-JSON
    sort key, since dicts are not orderable. This exercises the actual
    CORA shape (`Plan.wires: frozenset[Wire]`)."""

    @dataclass(frozen=True)
    class _Wire:
        kind: str
        value: int

    w1 = _Wire(kind="a", value=1)
    w2 = _Wire(kind="b", value=2)
    a = {"wires": frozenset([w1, w2])}
    b = {"wires": frozenset([w2, w1])}
    assert canonical_body_bytes(a) == canonical_body_bytes(b)


@pytest.mark.unit
def test_canonical_body_bytes_normalizes_nfd_strings_to_nfc() -> None:
    """German u-umlaut: NFC = single codepoint U+00FC; NFD = U+0075 + U+0308.
    Without recursive NFC, a copy-paste between editors silently
    produces two distinct hashes for "the same" identifier."""
    nfc = "Müller"  # 'Müller' precomposed
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd  # different byte sequences
    assert canonical_body_bytes({"name": nfc}) == canonical_body_bytes({"name": nfd})


@pytest.mark.unit
def test_canonical_body_bytes_normalizes_nfd_keys_to_nfc() -> None:
    """NFC recursion covers keys, not just values."""
    nfc_key = "Müller"
    nfd_key = unicodedata.normalize("NFD", nfc_key)
    assert canonical_body_bytes({nfc_key: 1}) == canonical_body_bytes({nfd_key: 1})


@pytest.mark.unit
def test_canonical_body_bytes_handles_dataclass_via_asdict() -> None:
    @dataclass(frozen=True)
    class _M:
        name: str
        count: int

    instance = _M(name="x", count=2)
    equivalent_dict = {"name": "x", "count": 2}
    assert canonical_body_bytes(instance) == canonical_body_bytes(equivalent_dict)


@pytest.mark.unit
def test_canonical_body_bytes_handles_nested_dataclass() -> None:
    @dataclass(frozen=True)
    class _Inner:
        value: int

    @dataclass(frozen=True)
    class _Outer:
        inner: _Inner
        name: str

    instance = _Outer(inner=_Inner(value=1), name="x")
    equivalent_dict = {"inner": {"value": 1}, "name": "x"}
    assert canonical_body_bytes(instance) == canonical_body_bytes(equivalent_dict)


# ---------- Idempotency ----------


@pytest.mark.unit
def test_canonical_body_bytes_idempotent() -> None:
    """Re-canonicalizing a parsed canonical form yields identical bytes.
    Important: a future code path that decodes canonical bytes and
    re-canonicalizes (for example, audit-mode verification) gets a
    stable round-trip."""
    import json

    body = {"a": frozenset([3, 1, 2]), "b": {"y": 2, "x": 1}}
    first = canonical_body_bytes(body)
    reparsed = json.loads(first.decode("utf-8"))
    second = canonical_body_bytes(reparsed)
    assert first == second


# ---------- Failure modes ----------


@pytest.mark.unit
def test_canonical_body_bytes_raises_value_error_on_nan() -> None:
    """NaN/Infinity are not valid JSON; allow_nan=False raises loudly.
    Better to fail at write time than to emit non-JSON tokens that
    silently break downstream consumers."""
    with pytest.raises(ValueError):
        canonical_body_bytes({"score": math.nan})


@pytest.mark.unit
def test_canonical_body_bytes_raises_value_error_on_infinity() -> None:
    with pytest.raises(ValueError):
        canonical_body_bytes({"score": math.inf})


@pytest.mark.unit
def test_canonical_body_bytes_raises_type_error_on_decimal() -> None:
    """Per design lock anti-hook #8, hashed aggregates may not
    introduce Decimal without revisiting the lock. Loud failure is
    the correct signal; the alternative (silent string-coercion)
    would hide schema drift."""
    with pytest.raises(TypeError):
        canonical_body_bytes({"price": Decimal("3.14")})


@pytest.mark.unit
def test_canonical_body_bytes_raises_type_error_on_bytes() -> None:
    with pytest.raises(TypeError):
        canonical_body_bytes({"blob": b"raw"})


@pytest.mark.unit
def test_canonical_body_bytes_raises_type_error_on_datetime() -> None:
    """Pydantic boundary converts datetime to ISO string before this
    helper sees the payload; a raw datetime arriving here is a bug
    upstream and should fail loudly."""
    from datetime import datetime

    with pytest.raises(TypeError):
        canonical_body_bytes({"at": datetime(2026, 5, 23)})


# ---------- Empty / boundary cases ----------


@pytest.mark.unit
def test_canonical_body_bytes_for_empty_dict() -> None:
    assert canonical_body_bytes({}) == b"{}"


@pytest.mark.unit
def test_canonical_body_bytes_for_none_value() -> None:
    assert canonical_body_bytes({"x": None}) == b'{"x":null}'


@pytest.mark.unit
def test_canonical_body_bytes_for_nested_empty_structures() -> None:
    assert canonical_body_bytes({"a": {}, "b": [], "c": frozenset()}) == (b'{"a":{},"b":[],"c":[]}')


# ---------- Golden vector (catches Pydantic / stdlib serialization drift) ----------


@pytest.mark.unit
def test_compute_content_hash_golden_vector() -> None:
    """A future stdlib `json` or Pydantic upgrade that subtly changes
    serialization would silently invalidate every historical hash.
    This vector is the canary; if it fails, do not regenerate it
    blindly, investigate the root cause first."""
    assert (
        compute_content_hash("application/vnd.cora.test+json", {"x": 1})
        == "a74753994507906500dd5cd216ad16c6b6822f8f484191c79443e1a3481e9e5c"
    )


@pytest.mark.unit
def test_canonical_body_bytes_frozenset_sorts_to_specific_order() -> None:
    """Pin the actual sorted order, not just equality across permutations.
    A regression that sorted on `id()` would produce stable hashes
    within a process but vary across processes; the equality test
    alone would pass under that regression. Pinning the output bytes
    catches it."""
    assert canonical_body_bytes({"tags": frozenset(["c", "a", "b"])}) == (b'{"tags":["a","b","c"]}')


# ---------- NFC normalization in list and frozenset leaves ----------


@pytest.mark.unit
def test_canonical_body_bytes_normalizes_nfd_strings_in_list_leaves() -> None:
    """NFC recursion must reach list elements, not only dict keys/values.
    A future refactor that hoists the NFC pass into the dict branch
    only would silently break this."""
    nfc = "Müller"
    nfd = unicodedata.normalize("NFD", nfc)
    assert canonical_body_bytes({"names": [nfc]}) == canonical_body_bytes({"names": [nfd]})


@pytest.mark.unit
def test_canonical_body_bytes_normalizes_nfd_strings_in_frozenset_leaves() -> None:
    """NFC recursion must reach frozenset elements too. Sort-by-canonical-JSON
    inside the set branch must operate on already-NFC-normalized strings."""
    nfc = "Müller"
    nfd = unicodedata.normalize("NFD", nfc)
    assert canonical_body_bytes({"names": frozenset([nfc])}) == canonical_body_bytes(
        {"names": frozenset([nfd])}
    )


@pytest.mark.unit
def test_canonical_body_bytes_collapses_nfd_and_nfc_keys_in_same_dict() -> None:
    """When both NFC and NFD spellings of the same identifier appear as
    dict keys in the same input, NFC normalization collapses them to
    one key. Last-write-wins per dict comprehension order. Pinned so
    a future change to the key-handling strategy is a deliberate
    decision, not a silent surprise."""
    nfc_key = "Müller"
    nfd_key = unicodedata.normalize("NFD", nfc_key)
    collapsed = canonical_body_bytes({nfc_key: 1, nfd_key: 2})
    # Either value may survive depending on dict ordering, but the
    # output must have exactly one key, named with the NFC form.
    assert collapsed in (b'{"M\xc3\xbcller":1}', b'{"M\xc3\xbcller":2}')


# ---------- Pathological inputs ----------


@pytest.mark.unit
def test_canonical_body_bytes_raises_recursion_error_on_deeply_nested_dict() -> None:
    """Pathological nesting hits CPython's recursion limit and raises
    `RecursionError`. Pinned so the failure mode is a loud crash, not
    a silent hang. Aggregates whose hashable subset could reach this
    depth must be rejected at schema-validation time, not here."""
    nested: dict[str, object] = {"x": 0}
    for _ in range(2000):
        nested = {"x": nested}
    with pytest.raises(RecursionError):
        canonical_body_bytes(nested)
