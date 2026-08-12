"""Write an exported record to disk as the bundle layout F5 names.

`project_record_export_v3.md`'s "Naming" section fixes the layout:
`manifest.json`, `streams.jsonl`, `logbooks/<kind>.jsonl`. Everything
upstream of this module produces in-memory structures; this is the step
that makes an artifact somebody can archive, cite, or email.

## Why JSON Lines, and the trap it carries

One row per line means a reader can stream a large export, `grep` it,
and see a per-row diff in review. The trap is that the bundle's line
format is NOT what the hashes cover. `compute_content_hash` hashes a
DSSE-PAE-wrapped, NFC-normalized, sorted-key serialization of the whole
BODY, so the on-disk file is a transport for the body, not the hashed
bytes themselves. Two consequences, both load-bearing:

- A verifier must REASSEMBLE the body (`{"streams": [...],
  "logbooks": {...}}`) from the files before hashing. `read_bundle_body`
  is that reassembly, and `scripts/verify_record_hash.py`'s
  `verify-bundle` subcommand reimplements it in stdlib-only form.
- Reordering lines, or losing one, changes the hash. That is the point:
  order is part of the record (F2's per-kind order key), not a
  presentation detail.

## Refusals

Writing into a non-empty directory refuses. A bundle is an atomic claim
about one database at one watermark; a directory holding two exports'
`logbooks/` files, or one export's `streams.jsonl` beside another's
`manifest.json`, would hash-verify per file and be a lie as a whole.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

from cora.infrastructure.record_export._hashing import (
    TwoTierRecord,
    hash_record,
    hash_redacted_record,
)
from cora.infrastructure.record_export._manifest import Manifest

MANIFEST_NAME = "manifest.json"
STREAMS_NAME = "streams.jsonl"
LOGBOOKS_DIR = "logbooks"

__all__ = [
    "LOGBOOKS_DIR",
    "MANIFEST_NAME",
    "STREAMS_NAME",
    "BundleDestinationNotEmptyError",
    "MalformedBundleError",
    "ManifestRecordMismatchError",
    "read_bundle_body",
    "write_bundle",
]


class BundleDestinationNotEmptyError(RuntimeError):
    """`write_bundle` was pointed at a directory that already holds files.

    Refuses rather than merging or overwriting: a bundle is one export's
    whole claim, and a directory mixing two exports would verify
    file-by-file while being incoherent as a record.
    """

    def __init__(self, destination: Path) -> None:
        super().__init__(
            f"refusing to write a bundle into non-empty directory {destination}: "
            "a bundle is one export at one watermark. Write to a fresh directory."
        )
        self.destination = destination


class MalformedBundleError(RuntimeError):
    """A directory does not hold a readable bundle.

    Raised for a missing `streams.jsonl`, a missing `manifest.json`, or a
    line that is not a JSON object. Never falls back to a partial read:
    a body reassembled from half a bundle would hash to something that
    matches nothing, which reads as tampering rather than as the file
    error it is.
    """


class ManifestRecordMismatchError(RuntimeError):
    """The manifest handed to `write_bundle` does not describe the record
    handed alongside it.

    `record` and `manifest` are two independent arguments with nothing
    structurally binding them together: nothing before this check
    verified that `manifest` was built FROM `record`. Reproduced
    concretely: passing the unredacted record next to a manifest whose
    `published_record_hash` was computed from the real redacted record
    wrote a self-consistently-formatted, fully unredacted bundle under a
    `--published` label, and the default verifier printed `OK`.
    `write_bundle` recomputes whichever of H1 or H3 the manifest claims
    over the record it was actually handed, before writing a single
    byte, and refuses on disagreement.
    """

    def __init__(self, *, expected: str, actual: str, published: bool) -> None:
        field = "published_record_hash (H3)" if published else "record_hash (H1)"
        super().__init__(
            f"refusing to write a bundle: the manifest's {field} is {expected!r}, but "
            f"the record handed to write_bundle hashes to {actual!r}. A bundle's "
            "manifest must describe the exact record written beside it."
        )
        self.expected = expected
        self.actual = actual


def _ensure_manifest_describes_record(record: TwoTierRecord, manifest: Manifest) -> None:
    """Which hash applies follows `manifest.published_record_hash`:
    present means this claims to be a published projection, so `record`
    must hash to H3; absent means an unredacted bundle, so `record` must
    hash to H1. Either branch also catches the mixed case (an unredacted
    `record` beside a manifest that carries H3, or vice versa), because
    the wrong-shaped record cannot reproduce the hash the manifest names.
    """
    if manifest.published_record_hash is not None:
        actual = hash_redacted_record(record)
        if actual != manifest.published_record_hash:
            raise ManifestRecordMismatchError(
                expected=manifest.published_record_hash, actual=actual, published=True
            )
        return
    actual = hash_record(record)
    if actual != manifest.record_hash:
        raise ManifestRecordMismatchError(
            expected=manifest.record_hash, actual=actual, published=False
        )


def _kind_filename(kind: str) -> str:
    """`logbooks/<kind>.jsonl`, with `kind` rejected if it could escape.

    Registry kinds are code-defined identifiers today, so this cannot
    currently fire. It is here because the alternative failure is
    writing outside the destination directory, and a kind reaches this
    function from a registry entry that a future edit could widen.
    """
    if not kind or "/" in kind or "\\" in kind or kind.startswith("."):
        message = f"logbook kind {kind!r} is not a safe filename component"
        raise MalformedBundleError(message)
    return f"{kind}.jsonl"


def _write_jsonl(path: Path, rows: tuple[dict[str, object], ...]) -> None:
    """One compact JSON object per line, in the order given.

    `sort_keys=True` is for reviewability of the file itself, not for
    the hash: the canonicalizer sorts independently, so a differently
    ordered file would still hash the same. Written together in one
    `write_text` so a partial line cannot survive a crash mid-export.
    """
    body = "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(body, encoding="utf-8")


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            message = f"{path.name} line {number} is not valid JSON: {exc}"
            raise MalformedBundleError(message) from exc
        if not isinstance(row, dict):
            message = f"{path.name} line {number} is a {type(row).__name__}, not a JSON object"
            raise MalformedBundleError(message)
        rows.append(cast("dict[str, object]", row))
    return tuple(rows)


def write_bundle(record: TwoTierRecord, manifest: Manifest, destination: Path) -> Path:
    """Write `record` and `manifest` as a bundle under `destination`.

    Creates the directory if absent; refuses if it exists with anything
    in it. Returns `destination` so a caller can chain.

    The manifest is written LAST. An interrupted export therefore leaves
    a directory with no `manifest.json`, which `read_bundle_body`
    refuses, rather than a complete-looking bundle whose row files are
    truncated.

    Raises `ManifestRecordMismatchError` before writing anything if
    `manifest` does not describe `record`: see that error's docstring.
    """
    _ensure_manifest_describes_record(record, manifest)
    destination.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in destination.iterdir())
    if existing:
        raise BundleDestinationNotEmptyError(destination)

    _write_jsonl(destination / STREAMS_NAME, record.streams)

    logbooks_dir = destination / LOGBOOKS_DIR
    logbooks_dir.mkdir()
    for kind, rows in record.logbooks.items():
        _write_jsonl(logbooks_dir / _kind_filename(kind), rows)

    manifest_path = destination / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(asdict(manifest), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def read_bundle_body(destination: Path) -> dict[str, object]:
    """Reassemble the hashed body from a bundle on disk.

    Returns exactly the structure `hash_record` / `hash_redacted_record`
    hash, so a caller can recompute either and compare. An empty
    `logbooks/` directory yields `{"logbooks": {}}`, which is a real
    export shape (a record with no entries rows at all), not an error.
    """
    streams_path = destination / STREAMS_NAME
    if not streams_path.is_file():
        message = f"{destination} has no {STREAMS_NAME}; not a bundle"
        raise MalformedBundleError(message)
    if not (destination / MANIFEST_NAME).is_file():
        message = (
            f"{destination} has no {MANIFEST_NAME}. The manifest is written last, "
            "so this is what an interrupted export leaves behind."
        )
        raise MalformedBundleError(message)

    logbooks_dir = destination / LOGBOOKS_DIR
    logbooks: dict[str, object] = {}
    if logbooks_dir.is_dir():
        for path in sorted(logbooks_dir.glob("*.jsonl")):
            logbooks[path.stem] = list(_read_jsonl(path))

    return {"streams": list(_read_jsonl(streams_path)), "logbooks": logbooks}
