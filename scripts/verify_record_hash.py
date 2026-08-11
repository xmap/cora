#!/usr/bin/env python3
"""Standalone content-hash verifier for a CORA record export.

Per `project_record_export_build_brief.md` step 5 and
`project_record_export_v3.md` F4: "sha256 and a JSON reader, no CORA" was
the earlier (falsified) claim -- `compute_content_hash` is SHA-256 over
DSSE-PAE-wrapped, NFC-normalized, sorted-key JSON, so a standalone
checker has to reimplement that canonicalization, not just hash raw
bytes. This file is that reimplementation: stdlib only (`json`,
`hashlib`, `unicodedata`, `argparse`), zero imports of `cora` or any
third-party package, so it runs with any Python 3.13 interpreter on a
machine that has never installed CORA.

This is deliberately NOT the full `cora.shared.content_hash` port. That
module also canonicalizes dataclasses, Pydantic models, and sets/
frozensets, because it hashes live domain objects elsewhere in CORA. A
record export never contains any of those: `render_row` (step 2)
already reduces every column to a JSON primitive before it reaches
`hash_record` (step 3), and the disposition table `hash_redaction_profile`
hashes (step 4) is itself a plain nested dict/str structure. So this
file's `_canonicalize` only has to handle what actually appears in an
exported body: `str`, `dict`, `list`/`tuple`, and JSON scalars passed
through unchanged. `tests/unit/infrastructure/record_export/
test_standalone_verifier.py` cross-checks this file byte-for-byte
against `cora.shared.content_hash.compute_content_hash` to keep the two
recipes from drifting apart.

Usage:
    python3 verify_record_hash.py hash --payload-type TYPE body.json
    python3 verify_record_hash.py verify --payload-type TYPE --expected-hash HASH body.json

Exit codes: 0 success (hash printed, or verify matched); 1 verify
mismatch; 2 the input file could not be read or parsed as JSON.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# `_canonicalize` deliberately takes `Any`, mirroring
# cora.shared.content_hash._canonicalize; suppressed the same way there.

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any


def _canonicalize(value: Any) -> Any:
    """Recursively normalize a value into a JSON-stable Python structure.

    Mirrors `cora.shared.content_hash._canonicalize`'s str/Mapping/list
    branches exactly (NFC normalization of strings and dict keys, list
    recursion); omits the dataclass/Pydantic/set branches, which never
    apply to an already-rendered export body (see module docstring).
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(k)): _canonicalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


def canonical_body_bytes(body: Any) -> bytes:
    """Produce canonical UTF-8 JSON bytes, byte-for-byte identical to
    `cora.shared.content_hash.canonical_body_bytes` for any body an
    export can actually contain."""
    canonical = _canonicalize(body)
    return json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def pae_bytes(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding, identical recipe to
    `cora.shared.content_hash.pae_bytes`. LEN is BYTE length, not
    character length: matters for a non-ASCII `payload_type`."""
    payload_type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 %d %b %d %b" % (
        len(payload_type_bytes),
        payload_type_bytes,
        len(body),
        body,
    )


def compute_content_hash(payload_type: str, body: Any) -> str:
    """SHA-256 content hash, 64-char lowercase hex. Identical pipeline to
    `cora.shared.content_hash.compute_content_hash`."""
    body_bytes = canonical_body_bytes(body)
    pae = pae_bytes(payload_type, body_bytes)
    return hashlib.sha256(pae).hexdigest()


def _load_body(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Standalone content-hash verifier for a CORA record export."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    hash_parser = subparsers.add_parser("hash", help="Print the content hash of a JSON body.")
    hash_parser.add_argument("--payload-type", required=True)
    hash_parser.add_argument("body_file", type=Path)

    verify_parser = subparsers.add_parser(
        "verify", help="Verify a JSON body's hash matches an expected value."
    )
    verify_parser.add_argument("--payload-type", required=True)
    verify_parser.add_argument("--expected-hash", required=True)
    verify_parser.add_argument("body_file", type=Path)

    args = parser.parse_args(argv)

    try:
        body = _load_body(args.body_file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read {args.body_file} as JSON: {exc}", file=sys.stderr)
        return 2

    digest = compute_content_hash(args.payload_type, body)

    if args.command == "hash":
        print(digest)
        return 0

    if digest == args.expected_hash:
        print(f"OK {digest}")
        return 0
    print(f"MISMATCH: expected {args.expected_hash}, computed {digest}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
