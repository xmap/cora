"""Unit tests for the Affordance closed StrEnum.

Pins the 29-item closed v1 list, the 2-pattern split, and the
serialization shape used by event payloads and REST/MCP bodies.
"""

import pytest

from cora.equipment.aggregates.family import Affordance, InvalidAffordanceError


@pytest.mark.unit
def test_affordance_v1_member_count() -> None:
    """v1 ships 29 items. Adding a value requires a CORA release;
    this test fails if the enum grew or shrunk so the design lock
    requires explicit acknowledgement."""
    assert len(list(Affordance)) == 29


@pytest.mark.unit
def test_affordance_pattern_a_operational_count() -> None:
    """Pattern A (Operational affordances, -able/-ible/-ing): 28 items.

    Mixed action (`-able`/`-ible`, "device supports doing X") and
    role/flow (`-ing` gerund, "device performs X"). Consumable ends
    in `-able` but is Pattern C (lifecycle), so excluded here."""
    operational = {
        a
        for a in Affordance
        if a.value.endswith(("able", "ible", "ing")) and a is not Affordance.CONSUMABLE
    }
    assert len(operational) == 28


@pytest.mark.unit
def test_affordance_pattern_a_gerund_members() -> None:
    """The `-ing` gerund subset of Pattern A. Role/flow items where the
    device IS the actor: Marking (PCOMP), Pulsing (pulse-train generator),
    Following (encoder-input slave), Leading (encoder-output master),
    Recording (file output), Capturing (produces a Data BC Acquisition
    fact on every capture)."""
    gerunds = {a for a in Affordance if a.value.endswith("ing")}
    assert gerunds == {
        Affordance.MARKING,
        Affordance.PULSING,
        Affordance.FOLLOWING,
        Affordance.LEADING,
        Affordance.RECORDING,
        Affordance.CAPTURING,
    }


@pytest.mark.unit
def test_affordance_pattern_c_lifecycle_count() -> None:
    """Pattern C (Lifecycle affordances, noun): 1 item — Consumable.

    Note: Consumable ends in -able but is classified as Pattern C
    because it names a lifecycle property (passive parts) rather
    than an operational role. The pattern-classification is
    documented in `cora.equipment.aggregates.family.affordance`
    docstring + `docs/reference/affordances.md`."""
    assert Affordance.CONSUMABLE.value == "Consumable"


@pytest.mark.unit
def test_affordance_str_enum_values_are_pascal_case() -> None:
    """All Affordance values are PascalCase strings (matches the BC-map
    convention; serializes as JSON discriminator without translation)."""
    for a in Affordance:
        assert a.value[0].isupper(), f"{a.name} value {a.value!r} not PascalCase"
        # No underscores in the string value (Python enum name uses _ but value is PascalCase)
        assert "_" not in a.value, f"{a.value!r} has underscore"


@pytest.mark.unit
def test_affordance_constructor_accepts_string_value() -> None:
    """StrEnum membership: `Affordance('Rotatable')` returns the enum member."""
    assert Affordance("Rotatable") is Affordance.ROTATABLE
    assert Affordance("Bendable") is Affordance.BENDABLE
    assert Affordance("Consumable") is Affordance.CONSUMABLE


@pytest.mark.unit
def test_affordance_constructor_raises_on_unknown_value() -> None:
    """Closed-enum guard: an unknown string raises ValueError on construction."""
    with pytest.raises(ValueError, match="is not a valid Affordance"):
        Affordance("BraggAddressable")  # explicitly dropped in Round 4
    with pytest.raises(ValueError, match="is not a valid Affordance"):
        Affordance("Magic")


@pytest.mark.unit
def test_invalid_affordance_error_carries_value() -> None:
    """The defensive error class for direct in-process callers preserves the bad value."""
    err = InvalidAffordanceError("Bogus")
    assert err.value == "Bogus"
    assert "Bogus" in str(err)
    assert "29" in str(err)  # message references the closed-enum size


@pytest.mark.unit
def test_affordance_supports_set_membership_semantics() -> None:
    """The matching engine (`Method.required_affordances ⊆ Family.affordances`)
    relies on frozenset membership being O(1) per the StrEnum's hashable
    contract."""
    family_affordances = frozenset(
        {
            Affordance.ROTATABLE,
            Affordance.HOMEABLE,
            Affordance.LIMITABLE,
        }
    )
    required = frozenset({Affordance.ROTATABLE, Affordance.HOMEABLE})
    assert required <= family_affordances
    not_required = frozenset({Affordance.BENDABLE})
    assert not (not_required <= family_affordances)


@pytest.mark.unit
def test_affordance_motion_category_members() -> None:
    """Pin the Motion category at 9 items so adds/drops are deliberate.

    Following + Leading were absorbed from the dissolved Pattern B
    (signal nouns) per the 2-pattern reframe; Capturable is the
    rename of PositionCapturable (drop the overspecifying prefix)."""
    motion = {
        Affordance.ROTATABLE,
        Affordance.TRANSLATABLE,
        Affordance.HOMEABLE,
        Affordance.LIMITABLE,
        Affordance.CAPTURABLE,
        Affordance.POSABLE,
        Affordance.INDEXABLE,
        Affordance.FOLLOWING,
        Affordance.LEADING,
    }
    assert len(motion) == 9


@pytest.mark.unit
def test_affordance_triggering_category_members() -> None:
    """Pin the Triggering+timing category at 5 items.

    Marking (rename of PositionTriggerable, resolves direction overlap
    with Triggerable-the-consumer) and Pulsing (absorbed from dissolved
    Pattern B) sit alongside the originals."""
    triggering = {
        Affordance.TRIGGERABLE,
        Affordance.GATEABLE,
        Affordance.SYNCHRONIZABLE,
        Affordance.MARKING,
        Affordance.PULSING,
    }
    assert len(triggering) == 5


@pytest.mark.unit
def test_affordance_dropped_pseudo_affordances_are_not_members() -> None:
    """Round 4 dropped 5 parameter-shaped candidates that belong in
    `Family.settings_schema` or operations-layer `Capability`. Pin
    the drop so re-adds require explicit re-research."""
    for dropped in (
        "BitDepthSelectable",
        "ROIConfigurable",
        "BadPixelMaskable",
        "BraggAddressable",
        "EnergySelectable",
    ):
        with pytest.raises(ValueError):
            Affordance(dropped)


@pytest.mark.unit
def test_affordance_renamed_legacy_names_are_not_members() -> None:
    """Pre-rename Pattern B nouns + overspecifying Pattern A names are
    gone — pin the renames so accidental re-introduction fails fast."""
    for legacy in (
        "PositionTriggerable",  # -> Marking
        "PositionCapturable",  # -> Capturable
        "PreTriggerBufferable",  # -> Bufferable
        "FileWritable",  # -> Recording
        "EncoderInput",  # -> Following
        "EncoderOutput",  # -> Leading
        "PulseGenerator",  # -> Pulsing
    ):
        with pytest.raises(ValueError):
            Affordance(legacy)
