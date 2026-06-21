"""Deterministic directory tree-hash for directory-output compute artifacts.

A reconstruction's default output is a DIRECTORY of files (a tomopy
`save-format=tiff` per-slice stack in `{stem}_rec/`), not a single file.
This helper folds such a directory into one deterministic sha256 digest
(the `sha256-tree` algorithm) so a folder-of-files carries the same
single verifiable fingerprint a single file does: a byte-identical copy
of the tree reproduces the same digest, and any change to the file set
or to any file's bytes changes it.

The digest is computed over an INJECTIVE binary stream, never a text
manifest. For each regular file, in sorted order, the running hash
absorbs the relpath byte-length (8-byte big-endian), then the relpath
bytes, then the 32 raw bytes of that file's sha256. Length-prefixing is
what makes the encoding injective: no filename (even one containing a
newline or spaces) can forge a different tree to the same digest, which
a delimited text manifest could not guarantee. Relpaths are NFC-
normalized so a copy moved between macOS (which readdir-returns NFD) and
Linux (NFC) hashes identically; the digest is therefore over LOGICAL
(NFC) paths, a deliberate choice. Symlinks are not followed and are
excluded from the tree; any other non-regular entry is a hard error.

This is the ONE place the canonicalization lives. The producer
(`LocalProcessComputePort`) and any future directory verifier MUST both
call `sha256_tree` so they can never drift. See
[[project_artifact_tree_hash_design]].
"""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from cora.operation.ports.compute_port import NonRegularTreeEntryError

if TYPE_CHECKING:
    from collections.abc import Iterator

_CHUNK = 1024 * 1024


def sha256_tree(root: Path) -> tuple[str, int, int]:
    """Return `(digest_hex, byte_size, entry_count)` for a directory tree.

    `digest_hex` is the 64-char lowercase `sha256-tree` digest;
    `byte_size` is the sum of regular-file sizes; `entry_count` is the
    number of regular files. Symlinks are skipped; a non-regular,
    non-symlink entry raises `_NonRegularTreeEntryError`. An empty tree
    returns `entry_count == 0`; the caller decides whether that is an
    error (the local-process adapter treats it as a missing artifact).
    """
    entries: list[tuple[bytes, Path, int]] = []
    for path, size in _regular_files(root):
        relpath = unicodedata.normalize("NFC", path.relative_to(root).as_posix())
        entries.append((relpath.encode("utf-8"), path, size))
    entries.sort(key=lambda entry: entry[0])

    running = hashlib.sha256()
    byte_size = 0
    for relpath_bytes, path, size in entries:
        running.update(len(relpath_bytes).to_bytes(8, "big"))
        running.update(relpath_bytes)
        running.update(_sha256_digest(path))
        byte_size += size
    return running.hexdigest(), byte_size, len(entries)


def _regular_files(root: Path) -> Iterator[tuple[Path, int]]:
    """Yield `(path, size)` for each regular file under `root`.

    Skips symlinks (does not follow them, so symlinked subtrees are
    excluded and link cycles cannot loop). Raises on any non-regular,
    non-symlink entry. Walk order is arbitrary; the caller sorts.
    """
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            info = path.lstat()
            mode = info.st_mode
            if stat.S_ISLNK(mode):
                continue
            if not stat.S_ISREG(mode):
                raise NonRegularTreeEntryError(str(path))
            yield path, info.st_size


def _sha256_digest(path: Path) -> bytes:
    """Stream a file through sha256, returning the raw 32-byte digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.digest()


__all__ = ["sha256_tree"]
