"""Unit tests for the `MonitorRef` value object.

Pins the bounded-text trim + length-check contract via the shared
`validate_bounded_text` helper. Mirrors the Supply MonitorRef test
shape (and fills the coverage gap on Supply's own MonitorRef).
"""

import pytest

from cora.enclosure.aggregates._value_types import (
    ENCLOSURE_MONITOR_SOURCE_ID_MAX_LENGTH,
    ENCLOSURE_MONITOR_SOURCE_KIND_MAX_LENGTH,
    InvalidMonitorRefError,
    MonitorRef,
)


@pytest.mark.unit
def test_monitor_ref_trims_both_components() -> None:
    ref = MonitorRef(source_kind="  EpicsPv  ", source_id="  S35:pss  ")
    assert ref.source_kind == "EpicsPv"
    assert ref.source_id == "S35:pss"


@pytest.mark.unit
def test_monitor_ref_empty_source_kind_raises() -> None:
    with pytest.raises(InvalidMonitorRefError):
        MonitorRef(source_kind="", source_id="ok")


@pytest.mark.unit
def test_monitor_ref_whitespace_only_source_kind_raises() -> None:
    with pytest.raises(InvalidMonitorRefError):
        MonitorRef(source_kind="   ", source_id="ok")


@pytest.mark.unit
def test_monitor_ref_empty_source_id_raises() -> None:
    with pytest.raises(InvalidMonitorRefError):
        MonitorRef(source_kind="EpicsPv", source_id="")


@pytest.mark.unit
def test_monitor_ref_source_kind_too_long_raises() -> None:
    with pytest.raises(InvalidMonitorRefError):
        MonitorRef(
            source_kind="x" * (ENCLOSURE_MONITOR_SOURCE_KIND_MAX_LENGTH + 1),
            source_id="ok",
        )


@pytest.mark.unit
def test_monitor_ref_source_id_too_long_raises() -> None:
    with pytest.raises(InvalidMonitorRefError):
        MonitorRef(
            source_kind="EpicsPv",
            source_id="x" * (ENCLOSURE_MONITOR_SOURCE_ID_MAX_LENGTH + 1),
        )


@pytest.mark.unit
def test_monitor_ref_at_max_length_accepted() -> None:
    ref = MonitorRef(
        source_kind="x" * ENCLOSURE_MONITOR_SOURCE_KIND_MAX_LENGTH,
        source_id="y" * ENCLOSURE_MONITOR_SOURCE_ID_MAX_LENGTH,
    )
    assert len(ref.source_kind) == ENCLOSURE_MONITOR_SOURCE_KIND_MAX_LENGTH
    assert len(ref.source_id) == ENCLOSURE_MONITOR_SOURCE_ID_MAX_LENGTH


@pytest.mark.unit
def test_monitor_ref_rejects_colon_in_source_kind() -> None:
    """`source_kind` may not contain ':' since the wire format joins
    `{source_kind}:{source_id}` on a colon and would otherwise fail to
    round-trip unambiguously. `source_id` may still contain colons
    (e.g. EPICS PV names) because the split is on the first colon only.
    """
    with pytest.raises(InvalidMonitorRefError):
        MonitorRef(source_kind="Epics:Pv", source_id="ok")


@pytest.mark.unit
def test_monitor_ref_allows_colon_in_source_id() -> None:
    """Colons in `source_id` are legal: the wire split is on the first
    colon, so a colon-bearing `source_id` round-trips cleanly."""
    ref = MonitorRef(source_kind="EpicsPv", source_id="S35:pss:permit")
    assert ref.source_id == "S35:pss:permit"
