"""CORA reads the BLEPS interlock's outcomes and never drives it.

BLEPS is the beamline equipment-protection interlock. It closes the
shutters when cooling water fails or a vacuum section trips, and a person
clears the latch at the panel. CORA's entire posture toward it, stated on
[#564](https://github.com/xmap/cora/issues/564) and in
`docs/deployments/2-bm/operations.md`, is that it observes and never
participates: it is not in the safety chain, and the argument for
declining a system-level "BLEPS Health" object rested on exactly that.

That posture is one grep away from being false. The IOC exposes write PVs
next to the read ones, and binding any of them would put CORA in the
interlock's command path:

  - `A_FAULT_RESET`, `TRIP_RESET`: clear every latched fault or trip
    across the whole system. These are the ones staff pointed at when
    they proposed CORA hold the reset surface.
  - `GVx_EPICS_OPEN`, `GVx_EPICS_CLOSE`: drive a gate valve.
  - `BIV_PERMIT`, `FES_PERMIT`, `SBS_PERMIT`: the interlock chain's
    command to a shutter. Readable, and per staff "in principle"
    writable, which is precisely why they are named here.

A future edit that reached for one of these would widen CORA from
observer to actor with no test failure, and the first evidence would be a
beamline noticing CORA had moved something. This turns it into a build
break.

## Scope: names, not directions

The scan looks for the PV leaf names anywhere in tracked source or in a
deployment descriptor, without trying to tell a read from a write. That
is deliberate and errs toward noisy: there is no legitimate reason to
name a BLEPS write PV in either place, so any appearance is worth a
conversation. Prose that discusses these PVs lives in `docs/`, which is
not scanned, and this module's own docstring is exempted below.
"""

from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files

# BLEPS write-side PV leaf names, from the `Outputs` and `EPICS_Inputs`
# classes of the deployed IOC's PV inventory (2bm-docs item_025.rst).
_WRITE_PV_LEAVES = (
    "A_FAULT_RESET",
    "TRIP_RESET",
    "GV1_EPICS_OPEN",
    "GV1_EPICS_CLOSE",
    "GV2_EPICS_OPEN",
    "GV2_EPICS_CLOSE",
    "GV3_EPICS_OPEN",
    "GV3_EPICS_CLOSE",
    "BIV_PERMIT",
    "FES_PERMIT",
    "SBS_PERMIT",
)

_THIS_FILE = "test_bleps_binding_is_read_only.py"


def _descriptor_files() -> list[Path]:
    """Deployment descriptors, where a PV binding would otherwise hide.

    `parents[4]` is the repository root: this file sits at
    `apps/api/tests/architecture/`, so parents run architecture, tests,
    api, apps, root. An earlier `parents[3]` pointed at `apps/deployments`,
    which does not exist, and `rglob` on a missing directory yields
    nothing, so the descriptor scan passed while reading zero files. Hence
    `test_the_descriptor_scan_reads_files` below: a guard that cannot tell
    "nothing to find" from "nowhere to look" is not a guard.
    """
    root = Path(__file__).resolve().parents[4] / "deployments"
    return sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))


@pytest.mark.architecture
def test_no_bleps_write_pv_is_named_in_source() -> None:
    offenders: list[str] = []
    for path in sorted(tracked_python_files()):
        if path.name == _THIS_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        offenders.extend(f"{path.name}: {leaf}" for leaf in _WRITE_PV_LEAVES if leaf in text)
    assert not offenders, (
        "CORA must never bind a BLEPS write PV; it observes the interlock "
        f"and never drives it (#564). Found: {offenders}"
    )


@pytest.mark.architecture
def test_no_bleps_write_pv_is_named_in_a_deployment_descriptor() -> None:
    offenders: list[str] = []
    for path in _descriptor_files():
        text = path.read_text(encoding="utf-8")
        offenders.extend(
            f"{path.parent.name}/{path.name}: {leaf}" for leaf in _WRITE_PV_LEAVES if leaf in text
        )
    assert not offenders, (
        "A deployment descriptor must not bind a BLEPS write PV; CORA "
        f"observes the interlock and never drives it (#564). Found: {offenders}"
    )


@pytest.mark.architecture
def test_the_write_pv_roster_is_not_silently_emptied() -> None:
    """Guards the guard: an empty roster would make both scans vacuous."""
    assert len(_WRITE_PV_LEAVES) >= 11
    assert "A_FAULT_RESET" in _WRITE_PV_LEAVES
    assert "TRIP_RESET" in _WRITE_PV_LEAVES


@pytest.mark.architecture
def test_the_descriptor_scan_reads_files() -> None:
    """Guards the other half: a wrong root made the descriptor scan vacuous.

    This is the check that was missing when `_descriptor_files()` pointed
    at a directory that does not exist. Asserting on the roster alone said
    nothing about whether anything was ever opened.
    """
    found = _descriptor_files()
    assert len(found) > 50, f"expected the deployments tree, found {len(found)} files"
    assert any(p.parent.name == "2-bm" for p in found)


@pytest.mark.architecture
def test_the_source_scan_reads_files() -> None:
    """Same guard for the source half, which shares the vacuous-scan risk."""
    assert len(tracked_python_files()) > 500
