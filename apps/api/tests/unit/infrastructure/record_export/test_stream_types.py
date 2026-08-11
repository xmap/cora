"""Unit tests for the closed `stream_type` set."""

import pytest

from cora.infrastructure.record_export import (
    KNOWN_STREAM_TYPES,
    UnknownStreamTypeError,
    ensure_stream_type_known,
)


@pytest.mark.parametrize("stream_type", sorted(KNOWN_STREAM_TYPES))
def test_ensure_stream_type_known_accepts_every_declared_stream_type(stream_type: str) -> None:
    ensure_stream_type_known(stream_type)  # must not raise


def test_ensure_stream_type_known_refuses_an_undeclared_stream_type() -> None:
    with pytest.raises(UnknownStreamTypeError) as excinfo:
        ensure_stream_type_known("Widget")
    assert excinfo.value.stream_type == "Widget"


def test_known_stream_types_has_no_empty_or_duplicate_entries() -> None:
    assert "" not in KNOWN_STREAM_TYPES
    assert len(KNOWN_STREAM_TYPES) == len({s.strip() for s in KNOWN_STREAM_TYPES})
