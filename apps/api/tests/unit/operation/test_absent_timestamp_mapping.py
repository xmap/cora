"""Unit-tier pin on the "substrate supplied no timestamp" rule.

Each adapter decides absence for itself, because each substrate spells
it differently: the EPICS adapters see a stamp sitting at the EPICS
epoch, Tango sees one at the Unix epoch, caproto may see no stamp
object at all. Four independent predicates mean four chances to drift,
and the integration tier can only reach them with a live IOC. This
file pins them against one expectation so a drift shows up in the fast
lane.

The rule: a reading cannot predate the clock that stamps it, so a
stamp at or before the substrate's own epoch is an ABSENT time rather
than an old one, and absence is reported as None instead of as a date
that parses. This catches a missing timestamp, never a wrong one; an
IOC whose clock is set to the wrong year reports a plausible stamp
that no adapter can detect.

Measured at APS 2-BM on 2026-08-09, which is why this exists: both
`S02BM-PSS:Sta[AB]:SecureM` report an undefined stamp on every
subscribe update, and the old code rendered that as
1990-01-01T00:00:00Z.
"""

from datetime import UTC, datetime

import pytest

from cora.operation.adapters.caproto_control_port import (
    _produced_at_for as caproto_produced_at_for,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.epics_ca_control_port import (
    _EPICS_EPOCH_UNIX_SECONDS,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.epics_ca_control_port import (
    _produced_at_for as ca_produced_at_for,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.epics_pva_control_port import (
    _produced_at_for as pva_produced_at_for,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.tango_control_port import (
    _produced_at_for as tango_produced_at_for,  # pyright: ignore[reportPrivateUsage]
)

_EPICS_EPOCH_SECONDS = 631152000.0
_REAL_READING_SECONDS = 1786280819.261532
_REAL_READING = datetime(2026, 8, 9, 13, 6, 59, 261532, tzinfo=UTC)


class _Stamp:
    """Minimal stand-in for caproto's `TimeStamp`, which exposes `as_datetime`."""

    def __init__(self, value: datetime) -> None:
        self._value = value

    def as_datetime(self) -> datetime:
        return self._value


class _TimeVal:
    """Minimal stand-in for Tango's `TimeVal`, which exposes `totime`."""

    def __init__(self, value: float) -> None:
        self._value = value

    def totime(self) -> float:
        return self._value


@pytest.mark.unit
def test_epics_epoch_constant_is_the_1990_boundary() -> None:
    """The magic number is 1990-01-01T00:00:00Z, stated once and checked here."""
    assert _EPICS_EPOCH_UNIX_SECONDS == _EPICS_EPOCH_SECONDS
    assert datetime.fromtimestamp(_EPICS_EPOCH_SECONDS, tz=UTC) == datetime(1990, 1, 1, tzinfo=UTC)


@pytest.mark.unit
@pytest.mark.parametrize("produced_at_for", [ca_produced_at_for, pva_produced_at_for])
def test_epics_stamp_at_the_epoch_is_absent(produced_at_for: object) -> None:
    """An EPICS record that never processed reports the epoch, not a 1990 reading."""
    assert produced_at_for(_EPICS_EPOCH_SECONDS) is None  # type: ignore[operator]


@pytest.mark.unit
@pytest.mark.parametrize("produced_at_for", [ca_produced_at_for, pva_produced_at_for])
def test_epics_stamp_before_the_epoch_is_absent(produced_at_for: object) -> None:
    """Nothing can be read before the clock starts, so earlier is absent too."""
    assert produced_at_for(0.0) is None  # type: ignore[operator]
    assert produced_at_for(-1.0) is None  # type: ignore[operator]


@pytest.mark.unit
@pytest.mark.parametrize("produced_at_for", [ca_produced_at_for, pva_produced_at_for])
def test_epics_real_stamp_is_preserved(produced_at_for: object) -> None:
    assert produced_at_for(_REAL_READING_SECONDS) == _REAL_READING  # type: ignore[operator]


@pytest.mark.unit
def test_epics_one_second_past_the_epoch_is_a_real_reading() -> None:
    """The boundary excludes only the epoch itself, not everything near it."""
    just_after = _EPICS_EPOCH_SECONDS + 1.0
    assert ca_produced_at_for(just_after) == datetime(1990, 1, 1, 0, 0, 1, tzinfo=UTC)
    assert pva_produced_at_for(just_after) == datetime(1990, 1, 1, 0, 0, 1, tzinfo=UTC)


@pytest.mark.unit
def test_caproto_missing_stamp_is_absent_not_wall_clock() -> None:
    """No stamp object at all answers None.

    This previously fell back to `datetime.now()`, which made an
    ingest time indistinguishable from a substrate time once written
    down. Pinned so the fallback cannot come back.
    """
    assert caproto_produced_at_for(None) is None
    assert caproto_produced_at_for(object()) is None


@pytest.mark.unit
def test_caproto_stamp_at_the_epoch_is_absent() -> None:
    assert caproto_produced_at_for(_Stamp(datetime(1990, 1, 1, tzinfo=UTC))) is None


@pytest.mark.unit
def test_caproto_real_stamp_is_preserved_and_utc_coerced() -> None:
    naive = _REAL_READING.replace(tzinfo=None)
    assert caproto_produced_at_for(_Stamp(naive)) == _REAL_READING
    assert caproto_produced_at_for(_Stamp(_REAL_READING)) == _REAL_READING


@pytest.mark.unit
def test_tango_boundary_is_the_unix_epoch_not_the_epics_one() -> None:
    """Tango counts from 1970, so its impossible boundary sits 20 years earlier.

    A Tango attribute stamped at the EPICS epoch is a genuine 1990
    reading as far as Tango is concerned, and must survive.
    """
    assert tango_produced_at_for(_TimeVal(0.0)) is None
    assert tango_produced_at_for(_TimeVal(-1.0)) is None
    assert tango_produced_at_for(None) is None
    assert tango_produced_at_for(_TimeVal(_EPICS_EPOCH_SECONDS)) == datetime(1990, 1, 1, tzinfo=UTC)


@pytest.mark.unit
def test_tango_real_stamp_is_preserved() -> None:
    assert tango_produced_at_for(_TimeVal(_REAL_READING_SECONDS)) == _REAL_READING


@pytest.mark.unit
def test_every_adapter_agrees_its_own_zero_is_absent() -> None:
    """Cross-adapter symmetry: whatever "nothing" looks like, the answer is None."""
    assert ca_produced_at_for(_EPICS_EPOCH_SECONDS) is None
    assert pva_produced_at_for(_EPICS_EPOCH_SECONDS) is None
    assert caproto_produced_at_for(_Stamp(datetime(1990, 1, 1, tzinfo=UTC))) is None
    assert tango_produced_at_for(_TimeVal(0.0)) is None
