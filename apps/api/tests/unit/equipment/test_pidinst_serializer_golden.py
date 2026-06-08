"""Byte-equal golden tests for the PIDINST v1.0 serializer.

Section 7.5 of the design memo. Each test builds a view from
`_pidinst_view_fixtures.py`, calls the serializer, canonicalises the
returned `PidinstRecord` via the shared
`cora.shared.content_hash.canonical_body_bytes` helper, and
asserts byte equality against the matching JSON fixture under
`pidinst_golden/` (read through the same canonicalizer for symmetric
trailing-newline handling).

When the schema mapping changes (slice D/E owner + persistent_id, or
future enrichment slices for description / measured-variable /
measurement-technique / related-identifier), the golden files
regenerate via `regenerate_pidinst_goldens.py` (gated on
COR_REGEN_GOLDENS=1) and are committed in the same PR as the rule
change. The golden file's git diff IS the documentation of the wire
shape change.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from cora.equipment._pidinst_serializer import to_pidinst_record
from cora.equipment._pidinst_types import AssetPidinstView
from cora.shared.content_hash import canonical_body_bytes
from tests.unit.equipment._helpers import (
    build_minimal_view,
    build_view_2bm_rotary_stage,
    build_view_with_alt_ids,
    build_view_with_hzb_owners,
    build_view_with_model,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_GOLDEN_DIR = Path(__file__).parent / "pidinst_golden"


def _assert_golden(fixture_name: str, view_builder: Callable[[], AssetPidinstView]) -> None:
    view = view_builder()
    record = to_pidinst_record(view)
    actual_bytes = canonical_body_bytes(record)
    expected_text = (_GOLDEN_DIR / f"{fixture_name}.json").read_text(encoding="utf-8")
    expected_bytes = canonical_body_bytes(json.loads(expected_text))
    assert actual_bytes == expected_bytes
    # Independent raw-text presence checks so the golden file cannot
    # accidentally validate as empty / structurally-different bytes that
    # the canonicalizer happens to normalize equivalently.
    assert f"urn:uuid:{view.asset_id}" in expected_text
    assert '"schema_version": "1.0"' in expected_text or '"schema_version":"1.0"' in expected_text


def test_to_pidinst_record_minimal_asset_golden_file_byte_equal() -> None:
    _assert_golden("minimal_asset", build_minimal_view)


def test_to_pidinst_record_asset_with_model_golden_file_byte_equal() -> None:
    _assert_golden("asset_with_model", build_view_with_model)


def test_to_pidinst_record_asset_with_alt_ids_golden_file_byte_equal() -> None:
    _assert_golden("asset_with_alt_ids", build_view_with_alt_ids)


def test_to_pidinst_record_2bm_rotary_stage_golden_file_byte_equal() -> None:
    _assert_golden("asset_2bm_rotary_stage", build_view_2bm_rotary_stage)


def test_to_pidinst_record_asset_with_hzb_owners_golden_file_byte_equal() -> None:
    """Slice D anchor: HZB record from F6.8 with full PIDINST Property
    5 payload (name + contact + ROR identifier + identifier_type).
    Asserts the slice D owners data substrate threads through to the
    serializer's canonical wire shape."""
    _assert_golden("asset_with_hzb_owners", build_view_with_hzb_owners)
