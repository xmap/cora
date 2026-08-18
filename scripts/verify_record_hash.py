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

`verify-bundle` also prints two verdicts, per
`project_record_completeness_design.md`'s "Verifier contract": `bundle:
COMPLETE` / `bundle: INCOMPLETE` (extent, resolved from
`extent_by_logbook_kind`) and `bundle: VALID` / `bundle: MISMATCH`
(integrity, the hash comparison above, restated in these locked terms).
Both are always printed; neither subcommand's own established output
(`OK <hash>` / `MISMATCH: ...`) changes. Extent is resolved only over
the kinds THIS MANIFEST declares -- the verifier has zero `cora`
imports, so it cannot see the registry, and a kind the manifest never
had a slot for is invisible to it by construction, not by oversight.
See `_resolve_extent`'s docstring for the three ways a bundle can come
back INCOMPLETE.

Exit codes: 0 success (hash printed, or verify matched, and for
`verify-bundle`, extent is also COMPLETE); 1 verify/integrity mismatch;
2 the input could not be read or parsed, OR the wrong mode was used for
this bundle (`verify-bundle` with no `--published` against a manifest
that carries `published_record_hash`, or `--published` against one that
does not); 3 `verify-bundle` only, reserved for INCOMPLETE-but-VALID: a
bundle whose hash checks out but whose own manifest declares a kind it
never traversed. A bundle that is both incomplete and invalid still
exits 1: integrity takes precedence, because a tampered bundle cannot
be trusted regardless of what its (possibly also tampered) extent claim
says about itself.
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


EXTENT_BY_LOGBOOK_KIND = "extent_by_logbook_kind"

STATUS_INCLUDED = "included"
STATUS_EXCLUDED = "excluded"
STATUS_UNTRAVERSED = "untraversed"
_KNOWN_STATUSES = frozenset({STATUS_INCLUDED, STATUS_EXCLUDED, STATUS_UNTRAVERSED})

RESIDUAL_NOTE = (
    "note: extent is resolved only from the kinds this bundle's own manifest "
    "declares and the rows actually present in its logbooks/ files. A kind "
    "never registered in the exporting checkout, or a row never reached by "
    "the exporter before export, is invisible to this check by construction "
    "-- that omission-at-origin signal (source_row_count) is computed "
    "in-process against the live database at export time, and is CORA-side "
    "only; this artifact carries its result but cannot reproduce the check. "
    "That in-process check has its own blind spot, not just this one: a row "
    "deleted from the database before export, or never written by the "
    "producing system at all, is invisible to it too, since both of its "
    "counts query the same already-diminished table. No verdict here speaks "
    "to either case."
)


def _resolve_extent(
    manifest: dict[str, Any], body: dict[str, Any]
) -> tuple[bool, list[str], list[str]]:
    """Resolve the extent verdict from what the manifest itself declares.

    Returns `(extent_ok, failures, excluded_kinds)`. Every kind is
    resolved and every failure collected before returning -- severity is
    not control flow, per `project_record_completeness_design.md`'s
    verifier contract, so a caller can report all of them at once rather
    than stopping at the first.

    Three independent ways a bundle comes back INCOMPLETE, each proven
    differentially in `test_standalone_verifier.py` (construct the bad
    manifest, assert this returns `extent_ok=False`):

    1. Any kind's status is `untraversed`: no code path in the exporting
       checkout ever reached that table, so the record cannot claim to
       be whole.
    2. The converse invariant: a kind marked `excluded` or `untraversed`
       whose bundle files nonetheless hold one or more rows. A kind
       claiming it was not read while its own file holds rows is a
       failure, not a curiosity -- nothing about the hash comparison
       catches this, since the manifest's status field is not part of
       the hashed body.
    3. A `source_row_count` of `null` on any kind whose status is NOT
       `untraversed`. `null` is permitted only there; an `included` (or
       `excluded`) kind with no independent count is a coverage field
       silently switched off, exactly the failure
       `project_independent_check_principle.md` exists to catch.

    `excluded` kinds are reported on their own line by the caller, never
    folded into this verdict: a kind can be `excluded` and still count
    toward COMPLETE, per the design's own status table.

    Only `included`/`excluded`/`untraversed` are resolvable statuses; an
    unrecognized one is reported as its own failure rather than silently
    ignored or guessed at.
    """
    extent = manifest.get(EXTENT_BY_LOGBOOK_KIND)
    if not isinstance(extent, dict) or not extent:
        return False, [f"manifest carries no usable {EXTENT_BY_LOGBOOK_KIND!r}"], []

    logbooks = body.get("logbooks")
    logbooks = logbooks if isinstance(logbooks, dict) else {}

    failures: list[str] = []
    excluded_kinds: list[str] = []
    any_untraversed = False

    for kind in sorted(extent):
        entry = extent[kind]
        if not isinstance(entry, dict):
            failures.append(f"{kind}: extent entry is not an object")
            continue
        status = entry.get("status")
        source_row_count = entry.get("source_row_count")
        rows = logbooks.get(kind)
        rows_present = len(rows) if isinstance(rows, list) else 0

        if status not in _KNOWN_STATUSES:
            failures.append(f"{kind}: unrecognized status {status!r}")
            continue

        if status == STATUS_UNTRAVERSED:
            any_untraversed = True
        if status == STATUS_EXCLUDED:
            excluded_kinds.append(kind)

        if status in (STATUS_EXCLUDED, STATUS_UNTRAVERSED) and rows_present != 0:
            failures.append(f"{kind}: marked {status} but the bundle holds {rows_present} row(s)")
        if status != STATUS_UNTRAVERSED and source_row_count is None:
            failures.append(f"{kind}: {status} but source_row_count is null")

    extent_ok = not any_untraversed and not failures
    return extent_ok, failures, excluded_kinds


def _verify_bundle(bundle: Path, *, published: bool) -> int:
    """Recompute a bundle's own hash, compare it to its manifest, and
    resolve the manifest's own extent claim against the bundle on disk.

    The manifest is read for the EXPECTED hash value only. That is not
    circular: the hash covers the two tiers, the manifest is not in
    them, so a tamperer who edits a row must also edit the manifest, and
    a tamperer who edits the manifest has changed the number a paper
    printed. Comparing against a hash quoted in a paper rather than in
    the bundle is strictly stronger, and is what `verify` (not
    `verify-bundle`) is for.

    Both verdicts are always computed and printed, even when one already
    determines the exit code: a reader scanning the output must be able
    to see both facts about the bundle, not just the one that won.
    Precedence for the exit code itself: integrity first. A bundle that
    is both incomplete and invalid exits 1, not 3, because a tampered
    bundle cannot be trusted to tell the truth about its own extent
    either -- `3` is reserved for a bundle whose hash genuinely checks
    out.
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
    hash_matches = digest == expected
    if hash_matches:
        print(f"OK {digest}")
    else:
        print(f"MISMATCH: manifest says {expected}, computed {digest}", file=sys.stderr)

    extent_ok, failures, excluded_kinds = _resolve_extent(manifest, body)

    print(f"bundle: {'COMPLETE' if extent_ok else 'INCOMPLETE'}")
    print("excluded kinds: " + (", ".join(excluded_kinds) if excluded_kinds else "none"))
    for failure in failures:
        print(f"extent failure: {failure}", file=sys.stderr)

    print(f"bundle: {'VALID' if hash_matches else 'MISMATCH'}")
    print(RESIDUAL_NOTE)

    if not hash_matches and not extent_ok:
        print(
            "note: bundle is both incomplete and invalid; exit code reflects "
            "integrity (1), not extent (3) -- see this function's own "
            "docstring for the precedence rule.",
            file=sys.stderr,
        )

    if not hash_matches:
        return 1
    if not extent_ok:
        return 3
    return 0


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
