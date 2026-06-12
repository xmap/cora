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
GRANDFATHERED_DECIDERS_WITHOUT_PBT: frozenset[str] = frozenset()


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
