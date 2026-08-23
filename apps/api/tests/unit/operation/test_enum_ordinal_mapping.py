"""Unit-tier pin on the "index behind an enum label" rule.

Sibling of `test_absent_timestamp_mapping.py` and it exists for the
same reason: each adapter derives `Measurement.ordinal` for itself,
because each substrate hands the index over differently (aioca's
`AugmentedValue` casts to it, p4p's NTEnum casts to it, PyTango gives a
bare int for `DevEnum`, caproto never resolves a label so its value IS
the index). Four independent predicates mean four chances to drift, and
the integration tier can only reach two of them without a live IOC or a
live Tango device. This file pins all four against one expectation so a
drift shows up in the fast lane.

The rule: for a two-state enum reading, `value` carries the facility's
label and `ordinal` carries the index behind it. The label is free text
a local engineer chose (`ZNAM` / `ONAM`, `enum_labels`,
`value.choices`); the index is 0 / 1 everywhere. Consumers asking a
yes/no question read the ordinal, so an adapter that silently stops
publishing it reverts that whole substrate to label matching, which
fails at any facility whose labels are not the conventional pair.

Measured at APS 2-BM on 2026-08-23, which is why this exists: the
`2bmBLEPS` IOC labels its flags `NO_FAULT` / `TRIP` and its fault and
comms flags `""` / `Present`. None of those four is in any conventional
set, so every BLEPS channel read as unbelievable and the observer
recorded nothing at all.

One adapter deliberately WITHHOLDS an ordinal it has, and that
asymmetry is pinned here too: Tango `DevState` indexes a global
device-state vocabulary (`ON = 0`), not a flag axis.
"""

from typing import Any

import pytest
from caproto import ChannelType

from cora.operation.adapters.caproto_control_port import (
    _to_reading as caproto_to_reading,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.epics_ca_control_port import (
    _enum_ordinal as ca_enum_ordinal,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.epics_pva_control_port import (
    _enum_ordinal as pva_enum_ordinal,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.tango_control_port import (
    _enum_ordinal as tango_enum_ordinal,  # pyright: ignore[reportPrivateUsage]
)
from cora.shared.binary_signal import binary_code

pytestmark = pytest.mark.unit

_BLEPS_PAIRS = (
    ("NO_FAULT", 0),
    ("TRIP", 1),
    ("", 0),
    ("Present", 1),
)
"""The four label / index pairs the deployed 2-BM BLEPS IOC publishes."""


class _CaEnum(int):
    """Stand-in for aioca's DBR_ENUM `AugmentedValue`, which casts to its index."""


class _PvaEnum(int):
    """Stand-in for p4p's NTEnum value, which casts to its index."""


class _Named:
    """A value carrying `.name`, the shape PyTango gives a `DevState`."""

    def __init__(self, name: str, index: int) -> None:
        self.name = name
        self._index = index

    def __int__(self) -> int:
        return self._index


class _TangoAttr:
    """Minimal stand-in for a Tango `DeviceAttribute`.

    `type.name` is what the adapter discriminates on, so it is modelled
    faithfully rather than inferred from the value's shape.
    """

    def __init__(self, value: Any, type_name: str) -> None:
        self.value = value
        self.type = _Named(type_name, 0)


class _CaprotoResponse:
    """Minimal stand-in for caproto's `ReadNotifyResponse` on an enum channel.

    `TIME_ENUM` is the type the adapter actually requests, and it is the
    reason this adapter never sees a label: `enum_strings` ride only on
    the CTRL types.
    """

    def __init__(self, *, index: int) -> None:
        self.data = [index]
        self.data_type = ChannelType.TIME_ENUM
        self.data_count = 1
        self.metadata = None


@pytest.mark.parametrize(("label", "index"), _BLEPS_PAIRS)
def test_every_adapter_reports_the_same_ordinal_for_the_same_index(label: str, index: int) -> None:
    """The one expectation all four predicates are held against.

    `label` is carried for realism and is deliberately NOT an input to
    any of these: an adapter that started deriving the ordinal from the
    label would pass its own test and fail this one.
    """
    assert ca_enum_ordinal(_CaEnum(index)) == index
    assert pva_enum_ordinal(_PvaEnum(index)) == index
    assert tango_enum_ordinal(_TangoAttr(index, "DevEnum"), "Categorical") == index


@pytest.mark.parametrize(("label", "index"), _BLEPS_PAIRS)
def test_every_adapters_ordinal_resolves_the_flag_the_label_cannot(label: str, index: int) -> None:
    """End of the chain: the index answers, the facility's word does not."""
    assert binary_code(label, ordinal=None) is None
    for ordinal in (
        ca_enum_ordinal(_CaEnum(index)),
        pva_enum_ordinal(_PvaEnum(index)),
        tango_enum_ordinal(_TangoAttr(index, "DevEnum"), "Categorical"),
    ):
        assert binary_code(label, ordinal=ordinal) == index


def test_caproto_reports_the_ordinal_despite_never_resolving_a_label() -> None:
    """The outlier adapter, and the reason it is not an exception.

    caproto reads TIME_ENUM, which carries no `enum_strings`, so it
    never resolves a label and its Categorical `value` is already the
    raw index. Publishing that same number as `ordinal` is what makes it
    answer a two-state question identically to the three adapters that
    do resolve labels. Before, the fleet disagreed on what a Categorical
    `value` even was (int here, str everywhere else) and only
    `binary_code` accepting both hid it.
    """
    reading = caproto_to_reading(_CaprotoResponse(index=1))
    assert reading.kind == "Categorical"
    assert reading.value == 1
    assert reading.ordinal == 1
    assert binary_code(reading.value, ordinal=reading.ordinal) == 1

    clear = caproto_to_reading(_CaprotoResponse(index=0))
    assert clear.ordinal == 0
    assert binary_code(clear.value, ordinal=clear.ordinal) == 0


def test_tango_devstate_withholds_its_ordinal_while_devenum_publishes() -> None:
    """The one deliberate asymmetry in the fleet, pinned so it stays deliberate.

    A `DevState` ordinal indexes Tango's global state vocabulary, where
    `ON = 0`, so a flag consumer reading it would resolve an ON device
    to false. The discriminator is the attribute TYPE, not a property of
    the value: a `DevState` arriving as a bare int must still be
    withheld, and a `DevEnum` whose value happens to carry `.name` must
    still be published.
    """
    assert tango_enum_ordinal(_TangoAttr(_Named("ON", 0), "DevState"), "Categorical") is None
    assert tango_enum_ordinal(_TangoAttr(0, "DevState"), "Categorical") is None
    assert tango_enum_ordinal(_TangoAttr(_Named("TRIP", 1), "DevEnum"), "Categorical") == 1


def test_no_adapter_reports_an_ordinal_for_a_non_categorical_reading() -> None:
    """`Measurement.ordinal` is documented as None for every other kind."""
    assert ca_enum_ordinal(_CaEnum(1)) == 1
    assert tango_enum_ordinal(_TangoAttr(1, "DevDouble"), "Scalar") is None
    assert tango_enum_ordinal(_TangoAttr(1, "DevEnum"), "Array") is None
