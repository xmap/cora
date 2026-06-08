"""Matrix coverage for the Asset evolver's `commissioned_at` /
`decommissioned_at` carry-forward (PIDINST v1.0 Property 11).

Two targeted regression tests for the originally-broken arms
(`AssetOwnerRemoved`, `AssetAttachedToFixture`) ship alongside the
fix itself in `test_asset_evolver.py`
(`test_evolve_asset_owner_removed_preserves_lifecycle_timestamps`,
`test_evolve_asset_attached_to_fixture_preserves_lifecycle_timestamps`).
This file mirrors the existing per-field parametrize convention
(`test_evolve_mutation_preserves_drawing`, `..._model_id`,
`..._alternate_identifiers`, etc.) and extends it to both lifecycle
dates across all 17 non-writer arms. The owner + fixture arms that
were absent from the older parametrize lists are explicitly included;
their omission is what allowed the bug to ship undetected.

Writers are exempt:
  - `AssetRegistered` is the genesis writer of `commissioned_at` (set
    from `occurred_at`); it does not carry forward (no prior state).
  - `AssetDecommissioned` is the terminal writer of
    `decommissioned_at` (set from `occurred_at`); it still carries
    forward `commissioned_at` from prior.

The companion architecture fitness test
(`tests/architecture/test_asset_evolver_lifecycle_dates_carry_forward.py`)
introspects the evolver source AST to catch the bug class when a new
arm is added without a matching parametrize entry here.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetActivated,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierRemoved,
    AssetAttachedToFixture,
    AssetDecommissioned,
    AssetDegraded,
    AssetDetachedFromFixture,
    AssetFamilyAdded,
    AssetFamilyRemoved,
    AssetFaulted,
    AssetLevel,
    AssetLifecycle,
    AssetMaintenanceEntered,
    AssetMaintenanceExited,
    AssetName,
    AssetOwner,
    AssetOwnerAdded,
    AssetOwnerName,
    AssetOwnerRemoved,
    AssetPortAdded,
    AssetPortRemoved,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetSettingsUpdated,
    evolve,
    fold,
)
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))
_COMMISSIONED_AT = datetime(2024, 5, 15, 9, 30, 0, tzinfo=UTC)
_DECOMMISSIONED_AT = datetime(2026, 4, 1, 14, 0, 0, tzinfo=UTC)
_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _prior(*, lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("X"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        commissioned_at=_COMMISSIONED_AT,
        decommissioned_at=_DECOMMISSIONED_AT,
    )


# ---------- Full carry-forward matrix (non-writer arms) ----------

# Mutation arms that must carry both lifecycle dates through. Mirrors
# the parametrize lists in test_asset_evolver.py
# (`test_evolve_mutation_preserves_alternate_identifiers`, etc.) and
# extends them with the owner + fixture arms whose absence in those
# lists is exactly what allowed the original regression.
_NON_WRITER_TRANSITIONS: list[tuple[str, type, dict[str, object]]] = [
    ("activate", AssetActivated, {}),
    ("enter_maintenance", AssetMaintenanceEntered, {}),
    ("exit_maintenance", AssetMaintenanceExited, {}),
    ("family_added", AssetFamilyAdded, {"family_id": uuid4()}),
    ("family_removed", AssetFamilyRemoved, {"family_id": uuid4()}),
    ("degraded", AssetDegraded, {"reason": "x"}),
    ("faulted", AssetFaulted, {"reason": "x"}),
    ("restored", AssetRestored, {"reason": "x"}),
    ("settings_updated", AssetSettingsUpdated, {"settings": {"a": 1}}),
    (
        "port_added",
        AssetPortAdded,
        {"port_name": "p1", "direction": "Input", "signal_type": "TTL"},
    ),
    ("port_removed", AssetPortRemoved, {"port_name": "p1"}),
    (
        "alt_id_added",
        AssetAlternateIdentifierAdded,
        {
            "alternate_identifier": AlternateIdentifier(
                kind=AlternateIdentifierKind.SERIAL_NUMBER, value="SN-1"
            ),
        },
    ),
    (
        "alt_id_removed",
        AssetAlternateIdentifierRemoved,
        {
            "alternate_identifier": AlternateIdentifier(
                kind=AlternateIdentifierKind.SERIAL_NUMBER, value="SN-1"
            ),
        },
    ),
    (
        "owner_added",
        AssetOwnerAdded,
        {"owner": AssetOwner(name=AssetOwnerName("ESRF"))},
    ),
    (
        "owner_removed",
        AssetOwnerRemoved,
        {"owner_name": AssetOwnerName("HZB")},
    ),
    (
        "fixture_attached",
        AssetAttachedToFixture,
        {"fixture_id": uuid4()},
    ),
    (
        "fixture_detached",
        AssetDetachedFromFixture,
        {"fixture_id": uuid4()},
    ),
]


def _pick_lifecycle_for(transition: type) -> AssetLifecycle:
    if transition is AssetActivated:
        return AssetLifecycle.COMMISSIONED
    if transition is AssetMaintenanceEntered:
        return AssetLifecycle.ACTIVE
    if transition is AssetMaintenanceExited:
        return AssetLifecycle.MAINTENANCE
    return AssetLifecycle.ACTIVE


def _seed_prior_for(transition: type) -> Asset:
    """Build a prior state with the bits each transition needs to
    survive (owner present for OwnerRemoved, fixture_id set for
    DetachedFromFixture, etc.)."""
    owners: frozenset[AssetOwner] = (
        frozenset({AssetOwner(name=AssetOwnerName("HZB"))})
        if transition is AssetOwnerRemoved
        else frozenset()
    )
    fixture_id = uuid4() if transition is AssetDetachedFromFixture else None
    return Asset(
        id=uuid4(),
        name=AssetName("X"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=_pick_lifecycle_for(transition),
        owners=owners,
        fixture_id=fixture_id,
        commissioned_at=_COMMISSIONED_AT,
        decommissioned_at=_DECOMMISSIONED_AT,
    )


@pytest.mark.unit
@pytest.mark.parametrize(("name", "transition", "kwargs"), _NON_WRITER_TRANSITIONS)
def test_evolve_non_writer_arm_preserves_commissioned_at(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Every non-writer arm carries `commissioned_at` forward. Writers
    (`AssetRegistered`) are tested separately."""
    _ = name
    prior = _seed_prior_for(transition)
    state = evolve(prior, transition(asset_id=prior.id, occurred_at=_NOW, **kwargs))
    assert state.commissioned_at == _COMMISSIONED_AT


@pytest.mark.unit
@pytest.mark.parametrize(("name", "transition", "kwargs"), _NON_WRITER_TRANSITIONS)
def test_evolve_non_writer_arm_preserves_decommissioned_at(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Every non-writer arm carries `decommissioned_at` forward.
    Writers (`AssetRegistered` defaults to None at genesis;
    `AssetDecommissioned` overwrites from `occurred_at`) are tested
    separately."""
    _ = name
    prior = _seed_prior_for(transition)
    state = evolve(prior, transition(asset_id=prior.id, occurred_at=_NOW, **kwargs))
    assert state.decommissioned_at == _DECOMMISSIONED_AT


# ---------- AssetRelocated preserves both ----------


@pytest.mark.unit
def test_evolve_asset_relocated_preserves_lifecycle_dates() -> None:
    """Hierarchy mutation also carries both dates."""
    prior = _prior()
    state = evolve(
        prior,
        AssetRelocated(
            asset_id=prior.id,
            from_parent_id=prior.parent_id or uuid4(),
            to_parent_id=uuid4(),
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert state.commissioned_at == _COMMISSIONED_AT
    assert state.decommissioned_at == _DECOMMISSIONED_AT


# ---------- Writer-arm behavior ----------


@pytest.mark.unit
def test_evolve_asset_registered_sets_commissioned_at_from_occurred_at() -> None:
    """Genesis writes commissioned_at from the event's occurred_at."""
    state = evolve(
        None,
        AssetRegistered(
            asset_id=uuid4(),
            name="X",
            level="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.commissioned_at == _NOW
    assert state.decommissioned_at is None


@pytest.mark.unit
def test_evolve_asset_decommissioned_sets_decommissioned_at_and_preserves_commissioned_at() -> None:
    """Terminal writer sets decommissioned_at from occurred_at AND
    carries commissioned_at through from prior."""
    asset_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="X",
                level="Unit",
                parent_id=uuid4(),
                occurred_at=_COMMISSIONED_AT,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.commissioned_at == _COMMISSIONED_AT
    assert state.decommissioned_at == _NOW
