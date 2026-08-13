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
    python3 verify_record_hash.py verify-bundle path/to/bundle/
    python3 verify_record_hash.py verify-bundle path/to/bundle/ --published

`verify-bundle` is the one a reviewer actually runs: point it at an
exported bundle directory and it reassembles the hashed body from
`streams.jsonl` plus `logbooks/*.jsonl`, recomputes the hash, and
compares against the manifest's own. `verify` is the stronger check,
because the expected hash comes from outside the bundle (a paper, a
DOI landing page) rather than from a file the same tamperer could edit.

Exit codes: 0 success (hash printed, or verify matched); 1 verify
mismatch; 2 the input could not be read or parsed, OR the wrong mode was
used for this bundle (`verify-bundle` with no `--published` against a
manifest that carries `published_record_hash`, or `--published` against
one that does not).
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


MANIFEST_NAME = "manifest.json"
STREAMS_NAME = "streams.jsonl"
LOGBOOKS_DIR = "logbooks"

RECORD_PAYLOAD_TYPE = "application/vnd.cora.record+json"
PUBLISHED_RECORD_PAYLOAD_TYPE = "application/vnd.cora.record-published+json"


def _read_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            message = f"{path.name} line {number} is not valid JSON: {exc}"
            raise ValueError(message) from exc
        if not isinstance(row, dict):
            message = f"{path.name} line {number} is not a JSON object"
            raise ValueError(message)
        rows.append(row)
    return rows


def read_bundle_body(bundle: Path) -> Any:
    """Reassemble the hashed body from a bundle directory on disk.

    Deliberately duplicates
    `cora.infrastructure.record_export._bundle.read_bundle_body`. That
    duplication is the same argument as the rest of this file: a checker
    that imported CORA's reassembly would confirm CORA's own idea of
    what the bundle says, which is not a check. Reassembly is part of
    what a verifier must independently believe, because a bundle whose
    files are correct individually can still be missing a whole logbook
    kind, and only the reassembled body's hash catches that.
    """
    streams_path = bundle / STREAMS_NAME
    if not streams_path.is_file():
        message = f"{bundle} has no {STREAMS_NAME}; not a bundle"
        raise ValueError(message)
    if not (bundle / MANIFEST_NAME).is_file():
        message = f"{bundle} has no {MANIFEST_NAME}; export may be incomplete"
        raise ValueError(message)

    logbooks: dict[str, Any] = {}
    logbooks_dir = bundle / LOGBOOKS_DIR
    if logbooks_dir.is_dir():
        for path in sorted(logbooks_dir.glob("*.jsonl")):
            logbooks[path.stem] = _read_jsonl(path)

    return {"streams": _read_jsonl(streams_path), "logbooks": logbooks}


def _verify_bundle(bundle: Path, *, published: bool) -> int:
    """Recompute a bundle's own hash and compare it to its manifest.

    The manifest is read for the EXPECTED value only. That is not
    circular: the hash covers the two tiers, the manifest is not in
    them, so a tamperer who edits a row must also edit the manifest, and
    a tamperer who edits the manifest has changed the number a paper
    printed. Comparing against a hash quoted in a paper rather than in
    the bundle is strictly stronger, and is what `verify` (not
    `verify-bundle`) is for.
    """
    try:
        body = read_bundle_body(bundle)
        manifest = _load_body(bundle / MANIFEST_NAME)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"cannot read bundle {bundle}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(manifest, dict):
        print(f"{MANIFEST_NAME} is not a JSON object", file=sys.stderr)
        return 2

    # The symmetric guard to the one four lines below. A bundle
    # whose manifest carries `published_record_hash` (H3) is structurally
    # a published projection -- checking it against `record_hash` (H1)
    # instead recomputes over the redacted body with the wrong payload
    # type, which mismatches for two independent reasons and prints
    # MISMATCH: byte-identical, on this CLI, to genuine tampering. Refuse
    # by the manifest's own shape, before ever comparing a digest.
    if not published and isinstance(manifest.get("published_record_hash"), str):
        print(
            "cannot verify: this bundle's manifest carries published_record_hash "
            "(H3), so it is a published projection. Checking it against "
            "record_hash (H1) would compare the redacted body to the unredacted "
            "record's hash and print MISMATCH, indistinguishable from tampering. "
            "Re-run with --published.",
            file=sys.stderr,
        )
        return 2

    field = "published_record_hash" if published else "record_hash"
    payload_type = PUBLISHED_RECORD_PAYLOAD_TYPE if published else RECORD_PAYLOAD_TYPE
    expected = manifest.get(field)
    if not isinstance(expected, str):
        detail = (
            "this bundle is not a published projection (its manifest carries no H3)"
            if published
            else "manifest has no record_hash"
        )
        print(f"cannot verify: {detail}", file=sys.stderr)
        return 2

    digest = compute_content_hash(payload_type, body)
    if digest == expected:
        print(f"OK {digest}")
        return 0
    print(f"MISMATCH: manifest says {expected}, computed {digest}", file=sys.stderr)
    return 1


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

    bundle_parser = subparsers.add_parser(
        "verify-bundle",
        help=(
            "Verify a bundle directory against the hash in its own manifest. "
            "Reads manifest.json, streams.jsonl and logbooks/*.jsonl."
        ),
    )
    bundle_parser.add_argument("bundle_dir", type=Path)
    bundle_parser.add_argument(
        "--published",
        action="store_true",
        help=(
            "Check the bundle against the manifest's published_record_hash (H3) "
            "instead of record_hash (H1). Use for a redacted bundle."
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "verify-bundle":
        return _verify_bundle(args.bundle_dir, published=args.published)

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
