"""Unit tests for the Run BC's reading-related state additions.

Covers:
  - `ChannelName` VO bounded-text contract
  - `InvalidChannelNameError` / `InvalidReadingValueError` /
    `InvalidSamplingProcedureError` shape
  - `RunReadingLogbookClosedError` shape
  - `SAMPLING_PROCEDURE_VALUES` set + the closed-enum lock
  - `READING_LOGBOOK_SCHEMA` round-trips through to_dict/from_dict
"""

from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    LOGBOOK_KIND_READING,
    READING_CHANNEL_NAME_MAX_LENGTH,
    READING_LOGBOOK_SCHEMA,
    READING_UNITS_MAX_LENGTH,
    SAMPLING_PROCEDURE_VALUES,
    ChannelName,
    InvalidChannelNameError,
    InvalidReadingValueError,
    InvalidSamplingProcedureError,
    RunReadingLogbookClosedError,
    RunStatus,
)
from cora.shared.logbook import LogbookSchema

# ---------- ChannelName VO ----------


@pytest.mark.unit
def test_channel_name_trims_whitespace() -> None:
    assert ChannelName("  T_sample  ").value == "T_sample"


@pytest.mark.unit
def test_channel_name_rejects_empty() -> None:
    with pytest.raises(InvalidChannelNameError):
        ChannelName("")


@pytest.mark.unit
def test_channel_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidChannelNameError):
        ChannelName("   ")


@pytest.mark.unit
def test_channel_name_accepts_max_length() -> None:
    name = "x" * READING_CHANNEL_NAME_MAX_LENGTH
    assert ChannelName(name).value == name


@pytest.mark.unit
def test_channel_name_rejects_over_max_length() -> None:
    with pytest.raises(InvalidChannelNameError):
        ChannelName("x" * (READING_CHANNEL_NAME_MAX_LENGTH + 1))


# ---------- Reading-value error class shapes ----------


@pytest.mark.unit
def test_invalid_reading_value_error_carries_value() -> None:
    """The diagnostic carries the offending value for operator clarity."""
    err = InvalidReadingValueError(float("nan"))
    assert "finite" in str(err).lower()


@pytest.mark.unit
def test_invalid_sampling_procedure_error_carries_allowed_set() -> None:
    """The diagnostic shows what values WERE allowed so operators can
    tell which procedure they should have used (and which are coming
    in future sub-phases)."""
    err = InvalidSamplingProcedureError("histogram", SAMPLING_PROCEDURE_VALUES)
    msg = str(err)
    assert "histogram" in msg
    # Allowed set is rendered (sorted for stable diagnostics).
    assert "baseline" in msg


# ---------- RunReadingLogbookClosedError shape ----------


@pytest.mark.unit
def test_run_reading_logbook_closed_error_carries_run_id_and_status() -> None:
    """Operator-facing diagnostic distinguishes "run never existed"
    (404) from "run is in a terminal status" (409 with the actual
    terminal stamped on the message)."""
    run_id = uuid4()
    err = RunReadingLogbookClosedError(run_id, RunStatus.COMPLETED)
    msg = str(err)
    assert str(run_id) in msg
    assert RunStatus.COMPLETED.value in msg
    assert err.current_status is RunStatus.COMPLETED


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal",
    [RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED, RunStatus.TRUNCATED],
)
def test_run_reading_logbook_closed_error_for_each_terminal(terminal: RunStatus) -> None:
    """Every terminal status renders cleanly (no exception during
    string formatting); pinned to catch any future enum value
    accidentally breaking the format string."""
    err = RunReadingLogbookClosedError(uuid4(), terminal)
    assert terminal.value in str(err)


# ---------- Closed-enum SAMPLING_PROCEDURE_VALUES ----------


@pytest.mark.unit
def test_sampling_procedure_values_locked_at_6f5c() -> None:
    """6f-5b shipped {'baseline'}; 6f-5c extends to add 'monitor'.
    Equality-pin (not membership) so any future addition is a
    deliberate, reviewable test edit. A stealth procedure addition
    would silently pass a membership check but WILL break this
    `==` comparison."""
    assert frozenset({"baseline", "monitor"}) == SAMPLING_PROCEDURE_VALUES


@pytest.mark.unit
def test_sampling_procedure_values_is_frozenset() -> None:
    """Frozenset signals 'closed enum, do not mutate at runtime'."""
    assert isinstance(SAMPLING_PROCEDURE_VALUES, frozenset)


# ---------- READING_LOGBOOK_SCHEMA ----------


@pytest.mark.unit
def test_reading_logbook_schema_declares_polymorphic_columns() -> None:
    """All RunReading columns are declared so projections can read
    entry shape uniformly. Includes the SOSA discriminator
    `sampling_procedure` and the three timestamps."""
    fields = READING_LOGBOOK_SCHEMA.fields
    assert "channel_name" in fields
    assert "value" in fields
    assert "units" in fields
    assert "sampling_procedure" in fields
    assert "sampled_at" in fields
    assert "occurred_at" in fields
    assert "recorded_at" in fields


@pytest.mark.unit
def test_reading_logbook_schema_value_field_typed_float() -> None:
    """Schema's value type matches the entry dataclass (float)."""
    assert READING_LOGBOOK_SCHEMA.fields["value"].type == "float"


@pytest.mark.unit
def test_reading_logbook_schema_round_trips_through_dict() -> None:
    """Schema serializes for jsonb storage and rebuilds losslessly.
    This is the path used by RunReadingLogbookOpened.payload."""
    raw = READING_LOGBOOK_SCHEMA.to_dict()
    rebuilt = LogbookSchema.from_dict(raw)
    assert rebuilt.fields == READING_LOGBOOK_SCHEMA.fields
    assert rebuilt.description == READING_LOGBOOK_SCHEMA.description


# ---------- LOGBOOK_KIND_READING ----------


@pytest.mark.unit
def test_logbook_kind_reading_constant_value() -> None:
    """The constant value lives on the wire (event payload kind field).
    Pinned to catch silent renames that would break event-stream
    interpretation across versions."""
    assert LOGBOOK_KIND_READING == "reading"


# ---------- Constants ----------


@pytest.mark.unit
def test_reading_units_max_length_locked() -> None:
    """Pinning the units bound; matches the API/Pydantic guard and
    the DDL CHECK constraint."""
    assert READING_UNITS_MAX_LENGTH == 64
