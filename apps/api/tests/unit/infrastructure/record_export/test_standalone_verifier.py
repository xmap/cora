"""Tests for the standalone, zero-cora-import verifier at
`scripts/verify_record_hash.py`.

Per `project_record_export_build_brief.md` step 5's acceptance: a unit
test cross-checking it byte-for-byte against `cora.shared.content_hash`
over a corpus including NFC and float cases; a subprocess test that
fails on a flipped byte.

The script is loaded via `importlib` for the byte-for-byte cross-check
(same dynamic-import bridge `tests/unit/deployments/test_beamline_descriptor.py`
uses for other `scripts/` modules, since `scripts/` is not on the
type-checker's or the `cora` package's path) and invoked as a genuine
subprocess for the CLI / flipped-byte tests, so at least one test proves
the file runs as an actual standalone OS process, not just an
importable module.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from cora.shared.content_hash import compute_content_hash as cora_compute_content_hash

if TYPE_CHECKING:
    from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[6]
_SCRIPT = _REPO_ROOT / "scripts" / "verify_record_hash.py"
_PAYLOAD_TYPE = "application/vnd.cora.record-test+json"

# Precomposed 'e-acute' (single codepoint U+00E9) vs decomposed ('e'
# U+0065 + combining acute accent U+0301). Both display as "e" with an
# accent but are different byte sequences until NFC-normalized.
_PRECOMPOSED_E_ACUTE = "café"
_DECOMPOSED_E_ACUTE = "café"


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_record_hash", _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verify_record_hash from {_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_record_hash"] = module
    spec.loader.exec_module(module)
    return module


_verifier = _load_verifier()

_CORPUS: list[Any] = [
    {"a": 1, "b": "text"},
    {"target_value": 423.0, "tolerance": 3.14159, "ramp_rate": 0.0},
    {"name": _PRECOMPOSED_E_ACUTE},
    {"name": _DECOMPOSED_E_ACUTE},
    {"flag": True, "missing": None},
    {"items": [{"k": "v"}, {"k2": [1, 2, 3]}], "nested": {"a": {"b": {"c": None}}}},
    {"turkish": "dotless ı vs dotted i İ", "emoji": "\U0001f52c"},  # noqa: RUF001
    [1, "two", 3.0, None, True, {"five": 5}],
    {},
    [],
    "bare string body",
    42,
]


def test_script_has_zero_cora_imports() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("import cora"), (
            f"{_SCRIPT} imports cora ({stripped!r}); the whole point of this "
            "file is running on a machine with no CORA installed."
        )
        assert not stripped.startswith("from cora"), (
            f"{_SCRIPT} imports cora ({stripped!r}); the whole point of this "
            "file is running on a machine with no CORA installed."
        )


@pytest.mark.parametrize("body", _CORPUS, ids=range(len(_CORPUS)))
def test_compute_content_hash_matches_cora_byte_for_byte(body: Any) -> None:
    assert _verifier.compute_content_hash(_PAYLOAD_TYPE, body) == cora_compute_content_hash(
        _PAYLOAD_TYPE, body
    )


def test_composed_and_decomposed_nfc_forms_hash_identically() -> None:
    assert _PRECOMPOSED_E_ACUTE != _DECOMPOSED_E_ACUTE  # different bytes pre-normalization
    composed = {"name": _PRECOMPOSED_E_ACUTE}
    decomposed = {"name": _DECOMPOSED_E_ACUTE}
    assert _verifier.compute_content_hash(
        _PAYLOAD_TYPE, composed
    ) == _verifier.compute_content_hash(_PAYLOAD_TYPE, decomposed)


def test_cli_hash_subcommand_prints_the_matching_digest(tmp_path: Path) -> None:
    body = {"a": 1, "b": _PRECOMPOSED_E_ACUTE}
    body_file = tmp_path / "body.json"
    body_file.write_text(json.dumps(body), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "hash", "--payload-type", _PAYLOAD_TYPE, str(body_file)],
        capture_output=True,
        text=True,
        check=True,
    )

    expected = cora_compute_content_hash(_PAYLOAD_TYPE, body)
    assert result.stdout.strip() == expected


def test_cli_verify_subcommand_exits_zero_on_a_match(tmp_path: Path) -> None:
    body = {"a": 1, "b": _PRECOMPOSED_E_ACUTE}
    body_file = tmp_path / "body.json"
    body_file.write_text(json.dumps(body), encoding="utf-8")
    expected = cora_compute_content_hash(_PAYLOAD_TYPE, body)

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "verify",
            "--payload-type",
            _PAYLOAD_TYPE,
            "--expected-hash",
            expected,
            str(body_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_verify_subcommand_fails_on_a_flipped_byte(tmp_path: Path) -> None:
    """The acceptance test named explicitly: a subprocess run against a
    tampered file must FAIL (nonzero exit), proving the recomputed hash
    is sensitive to the tamper rather than silently passing."""
    body = {"a": 1, "b": _PRECOMPOSED_E_ACUTE, "target_value": 423.0}
    body_file = tmp_path / "body.json"
    body_file.write_text(json.dumps(body), encoding="utf-8")
    expected = cora_compute_content_hash(_PAYLOAD_TYPE, body)

    def _verify() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "verify",
                "--payload-type",
                _PAYLOAD_TYPE,
                "--expected-hash",
                expected,
                str(body_file),
            ],
            capture_output=True,
            text=True,
        )

    before = _verify()
    assert before.returncode == 0

    # Flip exactly one character in the file's bytes on disk.
    original_text = body_file.read_text(encoding="utf-8")
    tampered_text = original_text.replace("423.0", "424.0")
    assert tampered_text != original_text
    body_file.write_text(tampered_text, encoding="utf-8")

    after = _verify()
    assert after.returncode == 1
    assert "MISMATCH" in after.stderr


def test_cli_reports_a_clean_error_on_unreadable_input(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "hash", "--payload-type", _PAYLOAD_TYPE, str(missing)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
