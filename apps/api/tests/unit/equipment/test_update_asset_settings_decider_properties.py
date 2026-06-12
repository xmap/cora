"""Property-based tests for `update_asset_settings.decide` (Equipment BC).

Complements the example-based `test_update_asset_settings_decider.py` with
universal claims across generated inputs. This is a cross-aggregate decider:
it takes an `AssetSettingsContext` carrying the Asset's bound Family streams
and validates the merged settings against the union of their schemas.

    (state, command, context, now) -> list[AssetSettingsUpdated]

Load-bearing properties:

  - Empty state always raises `AssetNotFoundError` carrying the command's
    asset_id (existence guard).
  - A patch that violates the bound Family's settings_schema always raises
    `InvalidAssetSettingsError` (disallowed condition).
  - A schema-valid patch that changes settings emits exactly one
    `AssetSettingsUpdated` keyed on state.id with occurred_at=now and the
    FULL post-merge dict in the payload.
  - Re-submitting the current value is a no-op (returns []).
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _asset(*, asset_id: UUID, settings: dict[str, Any] | None = None) -> Asset:
    cap_id = UUID(int=7)
    return Asset(
        id=asset_id,
        name=AssetName("Detector-X"),
        tier=AssetTier.DEVICE,
        parent_id=UUID(int=8),
        lifecycle=AssetLifecycle.ACTIVE,
        condition=AssetCondition.NOMINAL,
        family_ids=frozenset({cap_id}),
        settings=settings or {},
    )


def _capability(*, settings_schema: dict[str, Any] | None = None) -> Family:
    return Family(
        id=UUID(int=7),
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
@given(asset_id=st.uuids(), now=aware_datetimes())
def test_update_asset_settings_empty_state_raises_not_found(
    asset_id: UUID,
    now: datetime,
) -> None:
    """Empty state raises AssetNotFoundError carrying the command's asset_id."""
    with pytest.raises(AssetNotFoundError) as exc:
        update_asset_settings.decide(
            state=None,
            command=UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": 30}),
            context=AssetSettingsContext(families=[_energy_cap()]),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    energy=st.integers(min_value=51, max_value=200),
    now=aware_datetimes(),
)
def test_update_asset_settings_above_maximum_raises_invalid(
    asset_id: UUID,
    energy: int,
    now: datetime,
) -> None:
    """A merged value above the schema maximum raises InvalidAssetSettingsError."""
    state = _asset(asset_id=asset_id, settings={})
    with pytest.raises(InvalidAssetSettingsError):
        update_asset_settings.decide(
            state=state,
            command=UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": energy}),
            context=AssetSettingsContext(families=[_energy_cap()]),
            now=now,
        )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    rogue_key=printable_ascii_text(max_size=12),
    now=aware_datetimes(),
)
def test_update_asset_settings_orphan_key_raises_invalid(
    asset_id: UUID,
    rogue_key: str,
    now: datetime,
) -> None:
    """An unknown key not declared by any bound schema raises InvalidAssetSettingsError."""
    assume(rogue_key not in {"energy", "filter"})
    state = _asset(asset_id=asset_id, settings={})
    with pytest.raises(InvalidAssetSettingsError):
        update_asset_settings.decide(
            state=state,
            command=UpdateAssetSettings(asset_id=asset_id, settings_patch={rogue_key: "x"}),
            context=AssetSettingsContext(families=[_energy_cap()]),
            now=now,
        )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    energy=st.integers(min_value=5, max_value=50),
    now=aware_datetimes(),
)
def test_update_asset_settings_valid_change_emits_updated_with_merged_dict(
    asset_id: UUID,
    energy: int,
    now: datetime,
) -> None:
    """A schema-valid change emits one AssetSettingsUpdated keyed on state.id at now."""
    state = _asset(asset_id=asset_id, settings={"filter": "Cu"})
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": energy}),
        context=AssetSettingsContext(families=[_energy_cap()]),
        now=now,
    )
    assert events == [
        AssetSettingsUpdated(
            asset_id=state.id,
            settings={"filter": "Cu", "energy": energy},
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    energy=st.integers(min_value=5, max_value=50),
    now=aware_datetimes(),
)
def test_update_asset_settings_resubmit_current_value_returns_empty(
    asset_id: UUID,
    energy: int,
    now: datetime,
) -> None:
    """Re-submitting the current value is a no-op returning []."""
    state = _asset(asset_id=asset_id, settings={"energy": energy})
    events = update_asset_settings.decide(
        state=state,
        command=UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": energy}),
        context=AssetSettingsContext(families=[_energy_cap()]),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    energy=st.integers(min_value=5, max_value=50),
    now=aware_datetimes(),
)
def test_update_asset_settings_is_pure_same_input_same_output(
    asset_id: UUID,
    energy: int,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    state = _asset(asset_id=asset_id, settings={})
    command = UpdateAssetSettings(asset_id=asset_id, settings_patch={"energy": energy})
    context = AssetSettingsContext(families=[_energy_cap()])
    first = update_asset_settings.decide(state=state, command=command, context=context, now=now)
    second = update_asset_settings.decide(state=state, command=command, context=context, now=now)
    assert first == second
