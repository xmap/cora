"""Unit tests for the directory tree-hash helper (`sha256-tree`).

Cover determinism (independent of creation/walk order), the byte_size +
entry_count summary, nested directories, sensitivity to content and to
the path/content boundary (the injective-encoding guarantee the gate
review required), symlink exclusion, the non-regular-entry error, and
the empty-tree result.
"""

import hashlib
import os
from pathlib import Path

import pytest

from cora.operation.adapters._tree_hash import sha256_tree
from cora.operation.ports.compute_port import NonRegularTreeEntryError

_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _write(root: Path, relpath: str, content: bytes) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_same_tree_built_in_different_order_hashes_identically(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write(a, "x.tif", b"one")
    _write(a, "sub/y.tif", b"two")
    _write(b, "sub/y.tif", b"two")
    _write(b, "x.tif", b"one")

    assert sha256_tree(a) == sha256_tree(b)


def test_tree_reports_summed_byte_size_and_file_count(tmp_path: Path) -> None:
    _write(tmp_path, "a.tif", b"aaaa")
    _write(tmp_path, "nested/b.tif", b"bbbbbb")

    _digest, byte_size, entry_count = sha256_tree(tmp_path)

    assert byte_size == 10
    assert entry_count == 2


def test_changing_one_file_content_changes_the_digest(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write(a, "x.tif", b"one")
    _write(b, "x.tif", b"ONE")

    assert sha256_tree(a)[0] != sha256_tree(b)[0]


def test_renaming_a_file_changes_the_digest(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write(a, "x.tif", b"same")
    _write(b, "y.tif", b"same")

    assert sha256_tree(a)[0] != sha256_tree(b)[0]


def test_path_content_boundary_is_injective_no_collision(tmp_path: Path) -> None:
    # A naive delimiter-free or unprefixed encoding would hash file
    # name "x" + content "y" the same as name "xy" + content "": both
    # render the bytes "xy". Length-prefixing the path makes the two
    # trees distinguishable, which is the gate-review forgeability fix.
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write(a, "x", b"y")
    _write(b, "xy", b"")

    assert sha256_tree(a)[0] != sha256_tree(b)[0]


def test_symlinks_are_excluded_from_the_tree(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    linked = tmp_path / "linked"
    _write(plain, "real.tif", b"data")
    _write(linked, "real.tif", b"data")
    (linked / "alias.tif").symlink_to(linked / "real.tif")

    plain_result = sha256_tree(plain)
    linked_result = sha256_tree(linked)

    assert linked_result[2] == 1
    assert plain_result == linked_result


def test_non_regular_entry_raises(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("platform has no mkfifo")
    _write(tmp_path, "real.tif", b"data")
    os.mkfifo(tmp_path / "pipe")

    with pytest.raises(NonRegularTreeEntryError):
        sha256_tree(tmp_path)


def test_empty_tree_reports_zero_entries(tmp_path: Path) -> None:
    digest, byte_size, entry_count = sha256_tree(tmp_path)

    assert entry_count == 0
    assert byte_size == 0
    assert digest == _EMPTY_SHA256


def test_digest_is_64_lowercase_hex(tmp_path: Path) -> None:
    _write(tmp_path, "a.tif", b"x")

    digest, _byte_size, _entry_count = sha256_tree(tmp_path)

    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)
