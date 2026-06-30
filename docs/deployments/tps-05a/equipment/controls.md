# Controls

*The shutters, the motion controllers, and the seam between CORA and the floor, inherited from [TPS 07A](../../tps-07a/equipment/controls.md): an EPICS floor with a Blu-Ice/DCSS orchestration layer above it.*

## Shutters and triggering

The `WhiteBeamShutter` (a front-end PSS photon shutter) gates the white beam into the optics hutch; a `FastShutter` gates the per-oscillation exposure at the sample, synchronized with the omega sweep and the EIGER2 frames. The PV records are pending and the PSS permit-leaf signals are not in public source (PSS-1).

## Motion controllers

The endstation, goniometer-base, and detector stages run on EPICS motor records reached through the DHS bridge; the controller box firmware and IPs are not in public source (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and a DCSS-orchestrated EPICS floor

TPS 05A is the **same seam as [TPS 07A](../../tps-07a/equipment/controls.md)**, the 2-BM pattern at an MX beamline, applied to the cluster sibling. The structure has two tiers:

- **The floor: EPICS.** Every device (the MD3 goniometer, the EIGER2, the optics, stages, diagnostics) is an EPICS PV reached through an **EPICS Device Handler Server (DHS)**.
- **The orchestration: Blu-Ice/DCSS.** A **DCSS server** (the SSRL Distributed Control System lineage) commands the experiment in the DCS protocol (`stoh_start_oscillation`, `collectRuns`), reaching the floor through the DHS bridge. The Blu-Ice GUI is the operator's client.

CORA **owns** (its conducting engine, over the `ControlPort`): the rotation-MX collection (setting energy, positioning the detector distance, orienting the crystal, arming and triggering the detector through the oscillation), the mesh/grid-scan crystal location, and the autonomous sample-exchange loop, **assuming the role DCSS plays today**, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes): **EPICS** for the MD3, the EIGER2 control, the monochromator, attenuator, shutters, cryostream, stages, and diagnostics. The seam sits at the **DCS protocol boundary**: CORA's EdgeConductor replaces the DCSS scan/oscillation orchestration, conducting over the existing EPICS PVs, exactly as at 07A and at 2-BM.

The one difference from 07A is **evidential, not architectural**: 07A's seam was read directly from its control tree (the `DCSDHS` class, the DCS protocol verbs), while 05A has no dedicated tree. Its seam is inherited from the 07A reading and confirmed to apply by Chou et al., *J. Synchrotron Rad.* 2025, which states the Blu-Ice/DCS control interface for all three NSRRC MX endstations (TPS 05A, TPS 07A, TLS 15A1).

## Why Blu-Ice/DCSS, and not MXCuBE

Identical to the [07A reasoning](../../tps-07a/equipment/controls.md#why-blu-icedcss-and-not-mxcube): NSRRC is a formal [MXCuBE](https://github.com/mxcube/mxcubeweb) partner, but the live MX-cluster orchestration is Blu-Ice/DCSS, on high-confidence evidence (the 2025 paper covering 05A by name; the NSRRC code with zero `mxcubecore` presence; no `mxcubecore` HardwareObjects deployment for any NSRRC beamline). CORA models the **2-BM DCSS pattern, not the MX3/Manaca MXCuBE pattern**. A live MXCuBE config for 05A would flip the seam to mixed; its absence confirms Blu-Ice/DCSS (GONIO-1, [Open questions](../questions.md)).

The software interfaces (the `DCSS-server`, the `EPICS-DHS`, the `ISARA-robot`, `DECTRIS-SIMPLON`) are referenced by interface only, never registered as Assets.
