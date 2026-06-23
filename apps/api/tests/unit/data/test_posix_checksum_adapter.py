"""Unit tests for ``PosixChecksumAdapter`` (file:// ChecksumVerifier).

Covers the happy digest paths (Match / Mismatch) and every safety / I/O
failure that must collapse to ``Unreachable`` rather than raise: missing
file, a directory, a non-file scheme, a path outside the allowed roots, a
symlink that escapes the roots, and an unconfigured (empty-roots) adapter.
"""

import hashlib
from pathlib import Path
from uuid import uuid4

from cora.data.adapters import PosixChecksumAdapter
from cora.data.ports.checksum_verifier import Match, Mismatch, Unreachable

_SUPPLY_ID = uuid4()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _adapter(*roots: Path) -> PosixChecksumAdapter:
    return PosixChecksumAdapter(allowed_roots=tuple(str(r) for r in roots))


async def test_verify_returns_match_when_bytes_digest_to_expected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "scan.h5"
    payload = b"tomography frames" * 4096
    target.write_bytes(payload)

    result = await _adapter(root).verify(
        distribution_uri=target.as_uri(),
        expected_checksum=_sha256(payload),
        supply_id=_SUPPLY_ID,
    )

    assert result == Match(computed_checksum=_sha256(payload))


async def test_verify_returns_mismatch_with_actual_digest_when_bytes_differ(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "scan.h5"
    payload = b"actual bytes"
    target.write_bytes(payload)

    result = await _adapter(root).verify(
        distribution_uri=target.as_uri(),
        expected_checksum="a" * 64,
        supply_id=_SUPPLY_ID,
    )

    assert result == Mismatch(computed_checksum=_sha256(payload))


async def test_verify_returns_unreachable_for_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    missing = root / "absent.h5"

    result = await _adapter(root).verify(
        distribution_uri=missing.as_uri(),
        expected_checksum="a" * 64,
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)


async def test_verify_returns_unreachable_for_a_directory(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    result = await _adapter(root).verify(
        distribution_uri=root.as_uri(),
        expected_checksum="a" * 64,
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)


async def test_verify_returns_unreachable_for_non_file_scheme(tmp_path: Path) -> None:
    result = await _adapter(tmp_path).verify(
        distribution_uri="https://example.com/scan.h5",
        expected_checksum="a" * 64,
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)
    assert "file" in result.error_detail


async def test_verify_refuses_path_outside_allowed_roots(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    target = outside / "secret.h5"
    target.write_bytes(b"not yours")

    result = await _adapter(root).verify(
        distribution_uri=target.as_uri(),
        expected_checksum=_sha256(b"not yours"),
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)
    assert "outside the allowed roots" in result.error_detail


async def test_verify_refuses_symlink_escaping_the_roots(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    real_target = outside / "secret.h5"
    real_target.write_bytes(b"escaped")
    link = root / "link.h5"
    link.symlink_to(real_target)

    result = await _adapter(root).verify(
        distribution_uri=link.as_uri(),
        expected_checksum=_sha256(b"escaped"),
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)
    assert "outside the allowed roots" in result.error_detail


async def test_verify_with_no_configured_roots_refuses_every_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "scan.h5"
    target.write_bytes(b"data")

    result = await PosixChecksumAdapter(allowed_roots=()).verify(
        distribution_uri=target.as_uri(),
        expected_checksum=_sha256(b"data"),
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)


async def test_verify_returns_unreachable_for_embedded_null_byte(tmp_path: Path) -> None:
    # A fully-printable URI (file:///.../scan%00.h5) decodes to a path with a
    # null byte; os.path.realpath / open raise ValueError. The port contract
    # is never-raise, so this must surface as Unreachable, not a crash.
    root = tmp_path / "root"
    root.mkdir()
    uri = f"file://{root}/scan%00.h5"

    result = await _adapter(root).verify(
        distribution_uri=uri,
        expected_checksum="a" * 64,
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)


async def test_verify_returns_unreachable_for_remote_host(tmp_path: Path) -> None:
    result = await _adapter(tmp_path).verify(
        distribution_uri="file://otherhost/data/scan.h5",
        expected_checksum="a" * 64,
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)
    assert "remote host" in result.error_detail


async def test_verify_returns_unreachable_for_empty_path(tmp_path: Path) -> None:
    result = await _adapter(tmp_path).verify(
        distribution_uri="file://",
        expected_checksum="a" * 64,
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)


async def test_verify_does_not_confuse_prefix_sibling_root(tmp_path: Path) -> None:
    # A root of /.../data must NOT also contain /.../data2 (string-prefix trap).
    root = tmp_path / "data"
    sibling = tmp_path / "data2"
    root.mkdir()
    sibling.mkdir()
    target = sibling / "scan.h5"
    target.write_bytes(b"sibling")

    result = await _adapter(root).verify(
        distribution_uri=target.as_uri(),
        expected_checksum=_sha256(b"sibling"),
        supply_id=_SUPPLY_ID,
    )

    assert isinstance(result, Unreachable)
    assert "outside the allowed roots" in result.error_detail


def test_adapter_advertises_its_kind() -> None:
    assert PosixChecksumAdapter(allowed_roots=()).kind == "PosixChecksum"
