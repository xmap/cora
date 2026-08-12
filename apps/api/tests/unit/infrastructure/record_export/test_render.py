"""Unit tests for F6 rendering: `render_value` / `render_row`.

See `cora.infrastructure.record_export._render` for why this only
touches typed outer-row columns and must not recurse into jsonb.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from cora.infrastructure.record_export import (
    UndecodedJsonColumnError,
    render_row,
    render_value,
)

_SOME_UUID = UUID("12345678-1234-5678-1234-567812345678")


def test_uuid_renders_as_its_string_form() -> None:
    assert render_value(_SOME_UUID) == "12345678-1234-5678-1234-567812345678"


def test_utc_datetime_renders_as_iso8601() -> None:
    dt = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    assert render_value(dt) == "2026-05-31T12:00:00+00:00"


def test_session_local_offset_datetime_normalizes_to_utc() -> None:
    """The same instant at -05:00 must render identically to +00:00: this
    is the measured hazard F6 exists to close, not a stylistic choice."""
    minus_five = datetime(2026, 5, 31, 7, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    utc = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    assert render_value(minus_five) == render_value(utc) == "2026-05-31T12:00:00+00:00"


def test_bytes_renders_as_hex() -> None:
    assert render_value(b"\x00\xff\xab") == "00ffab"


def test_bytearray_and_memoryview_render_as_hex() -> None:
    assert render_value(bytearray(b"\x01\x02")) == "0102"
    assert render_value(memoryview(b"\x01\x02")) == "0102"


def test_plain_primitives_pass_through_unchanged() -> None:
    assert render_value("channel-a") == "channel-a"
    assert render_value(42) == 42
    assert render_value(3.14) == 3.14
    assert render_value(True) is True
    assert render_value(None) is None


def test_jsonb_decoded_dict_and_list_pass_through_unrendered() -> None:
    """payload/metadata already arrive as JSON-safe primitives (every
    to_payload() pre-converts UUID/datetime to strings before the row is
    written); render_value must not try to walk into them."""
    payload = {"logbook_id": "12345678-1234-5678-1234-567812345678", "kind": "activity"}
    assert render_value(payload) is payload
    assert render_value([1, "a", None]) == [1, "a", None]


def test_render_row_refuses_a_payload_that_arrived_as_a_string() -> None:
    """The shape a connection without jsonb codecs produces.

    Measured against the live 2-BM database: a raw `asyncpg.connect`
    hands `payload` back as text, and every later stage accepted it. The
    bundle was written, hashed, and the standalone verifier reported OK
    on a record whose payloads were strings, because the artifact was
    self-consistent about the wrong structure.
    """
    row: dict[str, object] = {
        "event_id": _SOME_UUID,
        "event_type": "EnclosurePermitObserved",
        "payload": '{"reason": "PSS permit observation", "trigger": "Monitor"}',
    }

    with pytest.raises(UndecodedJsonColumnError) as caught:
        render_row(row)

    assert caught.value.column == "payload"


def test_render_row_refuses_metadata_that_arrived_as_a_string() -> None:
    row: dict[str, object] = {
        "event_id": _SOME_UUID,
        "payload": {"a": 1},
        "metadata": '{"command": "ObserveEnclosureStatus"}',
    }

    with pytest.raises(UndecodedJsonColumnError) as caught:
        render_row(row)

    assert caught.value.column == "metadata"


def test_render_row_accepts_a_null_jsonb_column() -> None:
    row: dict[str, object] = {"payload": {"a": 1}, "metadata": None}

    assert render_row(row) == {"payload": {"a": 1}, "metadata": None}


def test_render_row_applies_render_value_to_every_column() -> None:
    row: dict[str, object] = {
        "event_id": _SOME_UUID,
        "occurred_at": datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC),
        "signature": b"\xde\xad",
        "event_type": "ProcedureRegistered",
        "payload": {"a": 1},
    }
    rendered = render_row(row)
    assert rendered == {
        "event_id": "12345678-1234-5678-1234-567812345678",
        "occurred_at": "2026-05-31T12:00:00+00:00",
        "signature": "dead",
        "event_type": "ProcedureRegistered",
        "payload": {"a": 1},
    }
