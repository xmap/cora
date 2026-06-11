"""Unit tests for the `update_asset_settings` slice's pure decider.

The decider:
  - Raises AssetNotFoundError on empty state
  - Merges patch into prior settings via RFC 7396 semantics
  - Validates merged result against union of supplied Capabilities'
    schemas (raises InvalidAssetSettingsError on validation failure)
  - No-ops (returns []) when merged equals current
  - Otherwise emits AssetSettingsUpdated with the FULL post-merge dict
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetSettingsUpdated,
    AssetTier,
    InvalidAssetSettingsError,
)
from cora.equipment.aggregates.family.state import (
    Family,
    FamilyName,
    FamilyStatus,
)
from cora.equipment.features import update_asset_settings
from cora.equipment.features.update_asset_settings import UpdateAssetSettings
from cora.equipment.features.update_asset_settings.context import AssetSettingsContext

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _asset(*, settings: dict[str, Any] | None = None) -> Asset:
    cap_id = uuid4()
    return Asset(
        id=uuid4(),
        name=AssetName("Detector-X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        condition=AssetCondition.NOMINAL,
        family_ids=frozenset({cap_id}),
        settings=settings or {},
    )


def _capability(*, settings_schema: dict[str, Any] | None = None) -> Family:
    return Family(
        id=uuid4(),
        name=FamilyName("Tomography"),
        status=FamilyStatus.DEFINED,
        settings_schema=settings_schema,
    )


def _energy_cap() -> Family:
    return _capability(
        settings_schema={
            "$schema": _DRAFT,
            "type": "object",
            "properties": {
                "energy": {
                    "type": "number",
                    "minimum": 5,
                    "maximum": 50,
                    "unit": {"system": "udunits", "code": "keV"},
                },
                "filter": {"type": "string"},
            },
        }
    )


@pytest.mark.unit
def test_decide_emits_event_when_setting_first_value() -> None:
    state = _asset(settings={})
    cap = _energy_cap()
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(asset_id=state.id, settings_patch={"energy": 30}),
        context=AssetSettingsContext(families=[cap]),
        now=_NOW,
    )
    assert events == [
        AssetSettingsUpdated(
            asset_id=state.id,
            settings={"energy": 30},
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_with_merged_dict_not_patch() -> None:
    """Pinned: event payload carries the FULL post-merge dict, NOT
    the patch. Readers don't have to fold prior events to reconstruct
    current state."""
    state = _asset(settings={"energy": 30, "filter": "Cu"})
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(asset_id=state.id, settings_patch={"energy": 40}),
        context=AssetSettingsContext(families=[_energy_cap()]),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].settings == {"energy": 40, "filter": "Cu"}


@pytest.mark.unit
def test_decide_emits_event_when_null_deletes_existing_key() -> None:
    state = _asset(settings={"energy": 30, "filter": "Cu"})
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(asset_id=state.id, settings_patch={"filter": None}),
        context=AssetSettingsContext(families=[_energy_cap()]),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].settings == {"energy": 30}


@pytest.mark.unit
def test_decide_no_op_when_merged_equals_current() -> None:
    """Re-submitting the same value is a no-op (matches 5g-a / 5g-b
    no-op-on-unchanged precedent)."""
    state = _asset(settings={"energy": 30})
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(asset_id=state.id, settings_patch={"energy": 30}),
        context=AssetSettingsContext(families=[_energy_cap()]),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_no_op_when_patch_is_empty_dict() -> None:
    """Empty patch leaves settings unchanged; no event."""
    state = _asset(settings={"energy": 30})
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(asset_id=state.id, settings_patch={}),
        context=AssetSettingsContext(families=[_energy_cap()]),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        update_asset_settings.decide(
            state=None,
            command=UpdateAssetSettings(asset_id=target_id, settings_patch={"x": 1}),
            context=AssetSettingsContext(families=[]),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_settings_for_constraint_violation() -> None:
    state = _asset(settings={})
    with pytest.raises(InvalidAssetSettingsError):
        update_asset_settings.decide(
            state=state,
            command=UpdateAssetSettings(
                asset_id=state.id,
                settings_patch={"energy": 1},  # below minimum=5
            ),
            context=AssetSettingsContext(families=[_energy_cap()]),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_settings_for_orphan_key_in_strict_mode() -> None:
    """Family has a schema; unknown key 'rogue' rejects."""
    state = _asset(settings={})
    with pytest.raises(InvalidAssetSettingsError):
        update_asset_settings.decide(
            state=state,
            command=UpdateAssetSettings(
                asset_id=state.id,
                settings_patch={"rogue": "x"},
            ),
            context=AssetSettingsContext(families=[_energy_cap()]),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_allows_null_cleanup_of_orphan_key_after_capability_removed() -> None:
    """Locked behavior: after a Family is removed, settings keys
    it owned become orphans on the Asset. PATCH writes that mention
    those keys with non-null values reject; PATCH writes with null
    are allowed (cleanup mechanism)."""
    state = _asset(settings={"energy": 30, "orphan_key": "leftover"})
    cap = _energy_cap()
    # Submit a patch that nulls the orphan key — must succeed and emit
    # an event with the cleaned-up settings.
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(
            asset_id=state.id,
            settings_patch={"orphan_key": None},
        ),
        context=AssetSettingsContext(families=[cap]),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].settings == {"energy": 30}


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(settings={})
    cap = _energy_cap()
    command = UpdateAssetSettings(asset_id=state.id, settings_patch={"energy": 30})
    first = update_asset_settings.decide(
        state=state, command=command, context=AssetSettingsContext(families=[cap]), now=_NOW
    )
    second = update_asset_settings.decide(
        state=state, command=command, context=AssetSettingsContext(families=[cap]), now=_NOW
    )
    assert first == second
