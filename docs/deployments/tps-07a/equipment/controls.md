# Controls

*The shutters, the motion controllers, and the seam between CORA and the floor, which at TPS 07A is an EPICS floor with a Blu-Ice/DCSS orchestration layer above it.*

## Shutters and triggering

The `WhiteBeamShutter` (a front-end PSS photon shutter) gates the white beam into the optics hutch; a `FastShutter` gates the per-oscillation exposure at the sample, synchronized with the omega sweep and the EIGER2 frames. The PV records are pending and the PSS permit-leaf signals are not in the public source (PSS-1). The rotation collection is the goniometer omega sweep synchronized with the detector frames; the concrete trigger wiring is part of the recipe layer (deferred at this design phase).

## Motion controllers

The endstation, goniometer-base, and detector stages run on EPICS motor records reached through the DHS bridge; the controller box firmware and IPs are not in the public tree (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and a DCSS-orchestrated EPICS floor

TPS 07A is the **2-BM seam at an MX beamline**. Unlike [MX3](../../mx3/equipment/controls.md), which spans four control planes at once, TPS 07A is a single EPICS floor with one orchestration layer above it. The structure has two tiers:

- **The floor: EPICS.** Every device (the MD3 goniometer, the EIGER2, the slits, attenuators, stages, diagnostics) is an EPICS PV, the beamline at `07a:` and the endstation at `07a-ES:`, reached through an **EPICS Device Handler Server (DHS)** (the `EpicsDHS` / `DCSDHS` class in the control tree, bridging to EPICS over `pyepics`).
- **The orchestration: Blu-Ice/DCSS.** A **DCSS server** per beamline (host `10.7.1.1`, port `14242`, the SSRL Distributed Control System lineage) commands the experiment in the DCS protocol (`stoh_start_oscillation`, `stoh_start_motor_move`, `stoh_register_operation`, `collectRuns`), reaching the floor through the DHS bridge. The Blu-Ice GUI is the operator's client to that server.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the rotation-MX collection: setting the energy, positioning the detector distance, orienting the crystal on the goniometer, and arming and triggering the detector through the oscillation, **assuming the role DCSS plays today** (`become_master`, `start_oscillation`, `collectRuns`);
- the mesh/grid-scan crystal location and the autonomous sample-exchange loop (the ISARA robot) as a Procedure, and the choice of what to collect, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- **EPICS** (via the DHS-equivalent PV layer) for the MD3 goniometer, the EIGER2 control, the monochromator, attenuator, shutters, cryostream, stages, and diagnostics, the `ControlPort` boundary CORA already knows from 2-BM and FXI.

The seam sits at the **DCS protocol boundary**: CORA's EdgeConductor replaces the DCSS scan/oscillation orchestration, conducting the MD3 + EIGER2 over the existing EPICS PVs, exactly as the 2-BM design replaces TomoScan's scan/alignment orchestration while leaving EPICS on the floor. The Blu-Ice GUI is the human edge CORA's spine/edge subsumes.

Frame egress (the EIGER2 ZMQ stream, migrating to DESY ASAP::O) moves over the `TransferPort` into CORA's Dataset of record, and the Dozor spot-scoring / CHiMP crystal-detection for mesh scans is `ComputePort` work, an **Observe / Compute leg, off the control seam**.

The software interfaces (the `DCSS-server`, the `EPICS-DHS`, the `ISARA-robot`, `DECTRIS-SIMPLON`, `ASAP::O`, `Dozor`, `CHiMP`) are referenced by interface only, never registered as Assets.

## Why Blu-Ice/DCSS, and not MXCuBE

NSRRC is a formal **MXCuBE collaboration partner** (listed alongside ESRF, SOLEIL, MAX IV, DESY in the [MXCuBE-Web](https://github.com/mxcube/mxcubeweb) README), so one might expect the MX cluster to run MXCuBE, the way Diamond, the Australian Synchrotron [MX3](../../mx3/index.md), and Sirius Manaca do. It does not. The live scan orchestration is **Blu-Ice/DCSS**, on high-confidence evidence:

- A 2025 peer-reviewed paper covering exactly these three MX endstations (TPS 07A, TPS 05A, TLS 15A1) states verbatim that *"the Blu-Ice/DCS software ... is adopted as the control interface for our endstations"*, with no MXCuBE mention (Chou et al., *J. Synchrotron Rad.* 2025).
- NSRRC's own control trees (last pushed December 2025) implement the DCSS wire protocol (`DCSDHS`, the `stoh_`/`htos_`/`stog_`/`gtos_` grammar) with **zero `mxcube` / `mxcubecore` presence**, and the official SPXF user site names exactly one beamline-control package: Blu-Ice.
- The MXCuBE evidence is partnership-level only: there is **no `mxcubecore` HardwareObjects / `beamline.yaml` deployment config** for any NSRRC beamline, the artifact every live MXCuBE site has.

So CORA models the **2-BM DCSS pattern, not the MX3/Manaca MXCuBE pattern**. Were a live MXCuBE `HardwareObjects` config for 07A to surface, the verdict would shift to mixed/in-transition; its absence confirms Blu-Ice/DCSS. This is the one question for staff that would settle it (GONIO-1, [Open questions](../questions.md)).
