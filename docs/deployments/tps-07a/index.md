# TPS 07A

*Micro-focus protein crystallography at the NSRRC Taiwan Photon Source: rotation MX on an Arinax MD3 microdiffractometer reading a DECTRIS EIGER2 X 16M, with an ISARA robot for unattended sample exchange. This page describes how CORA would model and run TPS 07A; the model is reverse-engineered from public configuration, not yet confirmed by NSRRC staff.*

| Property | Value |
| --- | --- |
| Asset | `TPS 07A` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSRRC](../nsrrc/index.md) (bound via `facility_code = "nsrrc"`, `FacilityKind = Site`) |
| Sector | EPICS PV namespace `07a:` (endstation at `07a-ES:`) |
| Institution | NSRRC, National Synchrotron Radiation Research Center, Hsinchu, Taiwan (context; not modeled as an Asset) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | TPS IU22 in-vacuum undulator, 6-20 keV, ~2.9 x 1.8 micron focal spot (front-end PV not in public source, SRC-1) |

!!! note "How CORA would land on TPS 07A"
    These pages describe how CORA would model, govern, and conduct TPS 07A, the first beamline of CORA's NSRRC Site, the [Taiwan Photon Source / Taiwan Light Source facility](../nsrrc/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, control interfaces, the seam) are read from public open source (the [`light911/NSRRC_TPS07A`](https://github.com/light911/NSRRC_TPS07A) control tree and the [`light911/TPS07A-Meshbest`](https://github.com/light911/TPS07A-Meshbest) mesh-scan app) and verified against it; the EPICS PV namespace is verified but per-device record strings, vendor part numbers, and physical positions are not, so they, and every read value, are carried `confirm` until staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: an EPICS floor with a Blu-Ice/DCSS orchestration seam

TPS 07A brings CORA to the **NSRRC Site** (its Taiwan facility) and a seam that is, deliberately, the **2-BM seam, not the MX3 seam**. Where the Australian Synchrotron [MX3](../mx3/index.md) drives the same MD3 + EIGER2 + ISARA kit over a *heterogeneous* control plane (EPICS plus the MXCuBE Exporter protocol plus SIMPLON REST plus a robot TCP), TPS 07A keeps everything on a **single EPICS floor** and puts the orchestration in a layer above it:

- **EPICS is the floor.** The MD3 goniometer, the EIGER2, the slits, attenuators, and diagnostics are all reachable as EPICS PVs (the beamline at `07a:`, the endstation at `07a-ES:`), through an **EPICS Device Handler Server (DHS)**.
- **Blu-Ice/DCSS is the orchestration.** A DCSS server per beamline (the SSRL Distributed Control System lineage) commands the oscillation, the motor moves, and the data collection (`stoh_start_oscillation`, `collectRuns`), and the DHS bridge translates those into EPICS `caput`/`caget`.

This is exactly the shape CORA already designed against at APS [2-BM](../2-bm/index.md), where EPICS is the floor and TomoScan is the orchestration layer CORA's edge replaces. **CORA's EdgeConductor would replace the DCSS scan/oscillation/`collectRuns` orchestration over the EPICS floor**, the direct analog of replacing TomoScan's scan/alignment orchestration. The choice of Blu-Ice/DCSS over MXCuBE is [confirmed live](equipment/controls.md#why-blu-icedcss-and-not-mxcube) (Chou et al., *J. Synchrotron Rad.* 2025; the NSRRC code, last pushed December 2025, carries zero MXCuBE presence), even though NSRRC is a formal MXCuBE partner.

The *technique*, rotation MX, is not new (Diamond [I03](../i03/index.md) brought it, and [MX3](../mx3/index.md) reinforced it), so TPS 07A introduces no new catalog Family and reuses i03's Goniometer and MX Methods. Its contribution is the new Site and the DCSS-over-EPICS seam at an MX beamline.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the storage-ring current monitor and the front-end shutter (the IU22 undulator source PV is not in the public tree, SRC-1), then the optics, the double-crystal monochromator over 6-20 keV, the master energy axis, the attenuator, and the micro-focus mirrors.
- [Sample](equipment/sample.md): the Arinax MD3 microdiffractometer goniometer, the cryostream cooling, and the beamstop, plus the ISARA sample-exchange robot.
- [Detector](equipment/detector.md): the DECTRIS EIGER2 X 16M, its translation stage with the 139 mm minimum-distance interlock, the on-axis viewing camera, and the beam-position diagnostics.

Cutting across all three:

- [Controls](equipment/controls.md): the shutters, the motion controllers, and the DCSS-over-EPICS orchestration seam.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the rotation-MX techniques TPS 07A runs (data collection, mesh/grid scan, autonomous sample exchange), each reusing a pending Diamond i03 Method.

## Governance

[Governance](governance.md): who may act at TPS 07A and the trust shape CORA applies; CORA brings its own per-Actor authority over the LDAP-backed staff and the mandatory training gate.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's TPS 07A content lives.
