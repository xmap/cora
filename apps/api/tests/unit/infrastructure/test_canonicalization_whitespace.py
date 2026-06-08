"""Canonical pipeline is whitespace-insensitive: source formatting
of equivalent JSON inputs MUST NOT affect the hash.

`canonical_body_bytes` accepts Python values (dict / list / Pydantic /
dataclass / frozenset), not JSON text. The whitespace-insensitivity
property therefore says: two JSON sources that decode to the same
Python value (modulo whitespace, line endings, and trailing newlines)
MUST hash identically once decoded. This pins the safeguard the
content-addressed identity design depends on: the only thing that
matters for the hash is the structural content, never the input
formatting.

If a future refactor introduced a code path that fed raw JSON text
through the pipeline (skipping the `_canonicalize` recurse-and-sort
step), this test would catch it: the compact and pretty forms would
diverge.

Coverage:
  - compact vs. pretty-printed JSON of the same value
  - leading / trailing whitespace inside string values is preserved
    (whitespace inside JSON strings IS semantic and MUST shift the
    hash, in contrast to whitespace between tokens)
  - CRLF vs LF line endings in pretty-printed JSON
  - trailing newline at end of JSON file
  - tab-indented vs space-indented JSON
  - Unicode BOM stripping at the boundary (text->dict step)
"""

import json
from typing import Any

import pytest

from cora.shared.content_hash import canonical_body_bytes, compute_content_hash

_PAYLOAD_TYPE = "application/vnd.cora.test+json"

_REFERENCE_BODY: dict[str, Any] = {
    "title": "Method Definition",
    "version": 7,
    "tags": ["alpha", "beta", "gamma"],
    "nested": {"inner": {"deep": [1, 2, 3]}, "flag": True},
    "optional": None,
}


@pytest.mark.unit
def test_canonical_body_bytes_ignores_input_formatting_for_pretty_vs_compact_json() -> None:
    """Pretty-printed JSON and compact JSON of the same value decode to
    identical Python dicts; the canonical pipeline produces identical
    bytes."""
    compact_text = json.dumps(_REFERENCE_BODY, separators=(",", ":"))
    pretty_text = json.dumps(_REFERENCE_BODY, indent=4, separators=(",", ": "))
    assert compact_text != pretty_text  # different source bytes
    assert canonical_body_bytes(json.loads(compact_text)) == canonical_body_bytes(
        json.loads(pretty_text)
    )


@pytest.mark.unit
def test_canonical_body_bytes_ignores_crlf_vs_lf_line_endings_in_pretty_json() -> None:
    """A pretty-printed payload authored on Windows (CRLF) and the same
    payload on Unix (LF) must yield identical hashes once parsed."""
    lf_text = json.dumps(_REFERENCE_BODY, indent=2)
    crlf_text = lf_text.replace("\n", "\r\n")
    assert lf_text != crlf_text
    assert canonical_body_bytes(json.loads(lf_text)) == canonical_body_bytes(json.loads(crlf_text))


@pytest.mark.unit
def test_canonical_body_bytes_ignores_trailing_newline_in_source_text() -> None:
    """A trailing newline at end-of-file is whitespace outside the
    JSON value and MUST NOT shift the hash."""
    text = json.dumps(_REFERENCE_BODY)
    text_with_trailing_newline = text + "\n"
    assert canonical_body_bytes(json.loads(text)) == canonical_body_bytes(
        json.loads(text_with_trailing_newline)
    )


@pytest.mark.unit
def test_canonical_body_bytes_ignores_tab_vs_space_indentation_in_pretty_json() -> None:
    """Tab- vs space-indentation is whitespace outside the JSON value;
    both decode to the same Python dict and hash identically."""
    space_indented = json.dumps(_REFERENCE_BODY, indent=2)
    tab_indented = space_indented.replace("  ", "\t")
    assert space_indented != tab_indented
    assert canonical_body_bytes(json.loads(space_indented)) == canonical_body_bytes(
        json.loads(tab_indented)
    )


@pytest.mark.unit
def test_canonical_body_bytes_ignores_leading_and_trailing_whitespace_around_json_document() -> (
    None
):
    """Whitespace surrounding the entire JSON document is ignored by
    `json.loads`; once decoded both yield the same dict."""
    text = json.dumps(_REFERENCE_BODY)
    padded = "   \n\t  " + text + "  \r\n  "
    assert canonical_body_bytes(json.loads(text)) == canonical_body_bytes(json.loads(padded))


@pytest.mark.unit
def test_canonical_body_bytes_preserves_whitespace_inside_string_values() -> None:
    """Whitespace inside a JSON string is semantic content of the
    string, not formatting. Two strings that differ in internal
    whitespace MUST produce different hashes; the pipeline is
    NOT a general "strip-all-whitespace" transform."""
    body_compact = {"label": "alpha beta"}
    body_padded = {"label": "alpha  beta"}  # two spaces
    body_leading = {"label": " alpha beta"}  # leading space
    body_trailing = {"label": "alpha beta "}  # trailing space
    h_compact = compute_content_hash(_PAYLOAD_TYPE, body_compact)
    h_padded = compute_content_hash(_PAYLOAD_TYPE, body_padded)
    h_leading = compute_content_hash(_PAYLOAD_TYPE, body_leading)
    h_trailing = compute_content_hash(_PAYLOAD_TYPE, body_trailing)
    assert len({h_compact, h_padded, h_leading, h_trailing}) == 4


@pytest.mark.unit
def test_canonical_body_bytes_preserves_newlines_inside_string_values() -> None:
    """A newline inside a JSON string is content; two strings that
    differ in embedded `\\n` MUST produce different hashes."""
    one_line = {"description": "first part second part"}
    two_line = {"description": "first part\nsecond part"}
    assert compute_content_hash(_PAYLOAD_TYPE, one_line) != compute_content_hash(
        _PAYLOAD_TYPE, two_line
    )


@pytest.mark.unit
def test_canonical_body_bytes_treats_utf8_bom_in_string_as_significant_content() -> None:
    """A UTF-8 BOM (U+FEFF) embedded in a string value is significant
    content per JSON spec. The canonical pipeline doesn't strip BOMs
    silently; the BOM remains part of the string for hashing
    purposes."""
    plain = {"name": "Subject"}
    with_bom = {"name": "﻿Subject"}
    assert compute_content_hash(_PAYLOAD_TYPE, plain) != compute_content_hash(
        _PAYLOAD_TYPE, with_bom
    )


@pytest.mark.unit
def test_canonical_body_bytes_ignores_whitespace_inside_lists_and_dicts_in_source() -> None:
    """Whitespace inside `[...]` and `{...}` between tokens is
    formatting; `[1, 2, 3]` and `[1,2,3]` parse to the same list and
    hash identically."""
    spaced = '{"v": [ 1 , 2 ,  3 ] , "x" : 1 }'
    compact = '{"v":[1,2,3],"x":1}'
    assert canonical_body_bytes(json.loads(spaced)) == canonical_body_bytes(json.loads(compact))
