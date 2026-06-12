"""Every decider must ship with a sibling property-based test.

Per the testing-expansion research memo and the Access/Trust PBT
pilots, each `<bc>/features/<slice>/decider.py` should be paired
with a `tests/unit/<bc>/test_<slice>_decider_properties.py`
property-based test. PBTs assert universal claims (purity,
event-shape stability, rejection-on-malformed) across generated
inputs, complementing the example-based `test_<slice>_decider.py`
sibling that pins specific scenarios.

This fitness gate walks every tracked `decider.py` and asserts
either:

  - the canonical sibling PBT path exists in `tests/unit/<bc>/`,
    matching the flat layout the Access / Trust pilots adopted, OR
  - the decider's qualified name is listed in
    `GRANDFATHERED_DECIDERS_WITHOUT_PBT` below.

`GRANDFATHERED_DECIDERS_WITHOUT_PBT` is an APPEND-ONLY-SHRINKING
allowlist. These deciders predate the PBT discipline; remove from
this list when the paired `*_decider_properties.py` lands. New
deciders MUST ship with a sibling PBT to land (no allowlist
additions).

The companion `test_grandfathered_deciders_still_lack_pbt` drift
catcher mirrors the WIP_DECIDERS precedent at
`test_decider_signature_canonical.py`: when a PBT lands, the
allowlist entry becomes dead weight and the drift catcher forces
its removal alongside the fix.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import (
    BCS,
    CORA_ROOT,
    tracked_python_files,
    tracked_test_files,
)

if TYPE_CHECKING:
    from pathlib import Path

# CORA_ROOT = apps/api/src/cora -> apps/api/tests
_TESTS_ROOT = CORA_ROOT.parent.parent / "tests"
_UNIT_ROOT = _TESTS_ROOT / "unit"

# Deciders that predate the property-based-test discipline. Each entry
# is a qualified module path (`cora.<bc>.features.<slice>.decider`)
# without a sibling `tests/unit/<bc>/test_<slice>_decider_properties.py`
# file. This list is APPEND-ONLY-SHRINKING: entries leave when a paired
# PBT lands; new deciders must NOT be added here.
GRANDFATHERED_DECIDERS_WITHOUT_PBT: frozenset[str] = frozenset(
    {
        "cora.access.features.forget_actor.decider",
        "cora.agent.features.define_agent.decider",
        "cora.agent.features.deprecate_agent.decider",
        "cora.agent.features.grant_tool_to_agent.decider",
        "cora.agent.features.promote_caution_proposal.decider",
        "cora.agent.features.regenerate_run_debrief.decider",
        "cora.agent.features.resume_agent.decider",
        "cora.agent.features.revise_agent_budget.decider",
        "cora.agent.features.revoke_tool_from_agent.decider",
        "cora.agent.features.suspend_agent.decider",
        "cora.agent.features.version_agent.decider",
        "cora.calibration.features.append_calibration_revision.decider",
        "cora.calibration.features.define_calibration.decider",
        "cora.campaign.features.abandon_campaign.decider",
        "cora.campaign.features.add_run_to_campaign.decider",
        "cora.campaign.features.close_campaign.decider",
        "cora.campaign.features.hold_campaign.decider",
        "cora.campaign.features.register_campaign.decider",
        "cora.campaign.features.remove_run_from_campaign.decider",
        "cora.campaign.features.resume_campaign.decider",
        "cora.campaign.features.start_campaign.decider",
        "cora.caution.features.register_caution.decider",
        "cora.caution.features.retire_caution.decider",
        "cora.caution.features.supersede_caution.decider",
        "cora.data.features.demote_dataset.decider",
        "cora.data.features.discard_dataset.decider",
        "cora.data.features.promote_dataset.decider",
        "cora.data.features.register_dataset.decider",
        "cora.decision.features.rate_decision.decider",
        "cora.decision.features.register_decision.decider",
        "cora.equipment.features.activate_asset.decider",
        "cora.equipment.features.add_asset_family.decider",
        "cora.equipment.features.add_asset_port.decider",
        "cora.equipment.features.decommission_asset.decider",
        "cora.equipment.features.decommission_frame.decider",
        "cora.equipment.features.decommission_mount.decider",
        "cora.equipment.features.define_family.decider",
        "cora.equipment.features.degrade_asset.decider",
        "cora.equipment.features.deprecate_family.decider",
        "cora.equipment.features.enter_asset_maintenance.decider",
        "cora.equipment.features.exit_asset_maintenance.decider",
        "cora.equipment.features.fault_asset.decider",
        "cora.equipment.features.install_asset.decider",
        "cora.equipment.features.register_frame.decider",
        "cora.equipment.features.relocate_asset.decider",
        "cora.equipment.features.remove_asset_family.decider",
        "cora.equipment.features.remove_asset_port.decider",
        "cora.equipment.features.restore_asset.decider",
        "cora.equipment.features.uninstall_asset.decider",
        "cora.equipment.features.update_asset_settings.decider",
        "cora.equipment.features.update_family_settings_schema.decider",
        "cora.equipment.features.update_frame_placement.decider",
        "cora.equipment.features.update_mount_placement.decider",
        "cora.equipment.features.version_family.decider",
        "cora.federation.features.abort_credential_rotation.decider",
        "cora.federation.features.activate_permit.decider",
        "cora.federation.features.complete_credential_rotation.decider",
        "cora.federation.features.complete_seal_republishing.decider",
        "cora.federation.features.initialize_seal.decider",
        "cora.federation.features.register_credential.decider",
        "cora.federation.features.resume_permit.decider",
        "cora.federation.features.revoke_credential.decider",
        "cora.federation.features.revoke_permit.decider",
        "cora.federation.features.rotate_seal_online_key.decider",
        "cora.federation.features.sign_seal_pointer.decider",
        "cora.federation.features.start_credential_rotation.decider",
        "cora.federation.features.start_seal_republishing.decider",
        "cora.federation.features.suspend_permit.decider",
        "cora.operation.features.abort_procedure.decider",
        "cora.operation.features.complete_procedure.decider",
        "cora.operation.features.register_procedure_from_recipe.decider",
        "cora.operation.features.start_procedure.decider",
        "cora.operation.features.truncate_procedure.decider",
        "cora.recipe.features.add_plan_wire.decider",
        "cora.recipe.features.define_method.decider",
        "cora.recipe.features.define_plan.decider",
        "cora.recipe.features.define_practice.decider",
        "cora.recipe.features.deprecate_capability.decider",
        "cora.recipe.features.deprecate_method.decider",
        "cora.recipe.features.deprecate_plan.decider",
        "cora.recipe.features.deprecate_practice.decider",
        "cora.recipe.features.deprecate_recipe.decider",
        "cora.recipe.features.remove_plan_wire.decider",
        "cora.recipe.features.update_method_parameters_schema.decider",
        "cora.recipe.features.update_plan_default_parameters.decider",
        "cora.recipe.features.version_capability.decider",
        "cora.recipe.features.version_method.decider",
        "cora.recipe.features.version_plan.decider",
        "cora.recipe.features.version_practice.decider",
        "cora.recipe.features.version_recipe.decider",
        "cora.run.features.abort_run.decider",
        "cora.run.features.adjust_run.decider",
        "cora.run.features.complete_run.decider",
        "cora.run.features.hold_run.decider",
        "cora.run.features.resume_run.decider",
        "cora.run.features.start_run.decider",
        "cora.run.features.stop_run.decider",
        "cora.run.features.truncate_run.decider",
        "cora.safety.features.activate_clearance.decider",
        "cora.safety.features.amend_clearance.decider",
        "cora.safety.features.append_clearance_review_step.decider",
        "cora.safety.features.approve_clearance.decider",
        "cora.safety.features.expire_clearance.decider",
        "cora.safety.features.register_clearance.decider",
        "cora.safety.features.reject_clearance.decider",
        "cora.safety.features.start_clearance_review.decider",
        "cora.safety.features.submit_clearance.decider",
        "cora.subject.features.discard_subject.decider",
        "cora.subject.features.dismount_subject.decider",
        "cora.subject.features.measure_subject.decider",
        "cora.subject.features.mount_subject.decider",
        "cora.subject.features.register_subject.decider",
        "cora.subject.features.remove_subject.decider",
        "cora.subject.features.return_subject.decider",
        "cora.subject.features.store_subject.decider",
        "cora.trust.features.abort_visit.decider",
        "cora.trust.features.arrive_visit.decider",
        "cora.trust.features.cancel_visit.decider",
        "cora.trust.features.check_in_visit.decider",
        "cora.trust.features.check_out_visit.decider",
        "cora.trust.features.complete_visit.decider",
        "cora.trust.features.define_conduit.decider",
        "cora.trust.features.define_policy.decider",
        "cora.trust.features.define_surface.decider",
        "cora.trust.features.hold_visit.decider",
        "cora.trust.features.register_visit.decider",
        "cora.trust.features.release_control_of_surface.decider",
        "cora.trust.features.resume_visit.decider",
        "cora.trust.features.start_visit.decider",
        "cora.trust.features.take_control_of_surface.decider",
        "cora.trust.features.void_visit.decider",
    }
)


def _decider_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        out.extend(
            sorted(
                f
                for f in tracked
                if f.name == "decider.py"
                and f.parent.parent == features
                and not f.parent.name.startswith("_")
            )
        )
    return out


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _expected_pbt_path(decider: Path) -> Path:
    """Map `<bc>/features/<slice>/decider.py` to the canonical PBT path.

    The flat layout the Access / Trust pilots adopted lives at
    `tests/unit/<bc>/test_<slice>_decider_properties.py`. Slice-nested
    test layouts are NOT supported (no PBT in the codebase uses one
    today; adopt-then-relax if a sub-slice variant ever appears).
    """
    slice_dir = decider.parent
    bc = slice_dir.parent.parent.name
    slice_name = slice_dir.name
    return _UNIT_ROOT / bc / f"test_{slice_name}_decider_properties.py"


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _decider_files(), ids=_qualified)
def test_decider_has_paired_property_based_test(decider: Path) -> None:
    """Decider must ship with a sibling `*_decider_properties.py` PBT
    (or be listed in `GRANDFATHERED_DECIDERS_WITHOUT_PBT`).
    """
    qualified = _qualified(decider)
    if qualified in GRANDFATHERED_DECIDERS_WITHOUT_PBT:
        pytest.skip(f"{qualified} is grandfathered (predates PBT discipline)")
    expected_pbt = _expected_pbt_path(decider)
    assert expected_pbt in tracked_test_files(), (
        f"{qualified}: missing paired property-based test.\n"
        f"  Expected: {expected_pbt.relative_to(_TESTS_ROOT.parent)}\n"
        "  Author a sibling PBT mirroring the Access / Trust pilots "
        "(see tests/unit/access/test_register_actor_decider_properties.py "
        "for the template), or, if no property template applies yet, add "
        "the qualified name to GRANDFATHERED_DECIDERS_WITHOUT_PBT in "
        "tests/architecture/test_decider_changes_require_paired_pbt.py."
    )


@pytest.mark.architecture
def test_grandfathered_deciders_still_lack_pbt() -> None:
    """`GRANDFATHERED_DECIDERS_WITHOUT_PBT` entries must still lack a PBT.

    Drift catcher: once a paired PBT lands, the allowlist entry becomes
    dead weight. Re-running the existence check here forces the
    allowlist entry to be removed alongside the fix. Mirrors
    `test_wip_deciders_still_violate` at
    `test_decider_signature_canonical.py`.
    """
    tracked_tests = tracked_test_files()
    for qualified in GRANDFATHERED_DECIDERS_WITHOUT_PBT:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        decider_path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert decider_path.is_file(), (
            f"GRANDFATHERED entry {qualified}: decider file no longer exists; "
            "remove the allowlist entry."
        )
        expected_pbt = _expected_pbt_path(decider_path)
        assert expected_pbt not in tracked_tests, (
            f"GRANDFATHERED entry {qualified}: a paired PBT now exists at "
            f"{expected_pbt.relative_to(_TESTS_ROOT.parent)}. Remove the "
            "allowlist entry."
        )
