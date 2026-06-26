# FMX

*Frontier Microfocusing Macromolecular Crystallography at NSLS-II, beamline 17-ID-2: microfocus rotation MX data collection on a single-omega goniometer and an Eiger detector, with an autonomous robotic sample changer. This page describes how CORA would model and run FMX; the model is reverse-engineered from public configuration, not yet confirmed by FMX staff.*

| Property | Value |
| --- | --- |
| Asset | `FMX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 17` (PV namespace `XF:17ID*`, the 17-ID-2 branch) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | IVU21 in-vacuum undulator on the NSLS-II 3 GeV ring (shared with AMX on the 17-ID straight) |

!!! note "How CORA would land on FMX"
    These pages describe how CORA would model, govern, and conduct FMX, the fourteenth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), [SIX](../six/index.md), [CHX](../chx/index.md), [CSX](../csx/index.md), [XPD](../xpd/index.md), [ESM](../esm/index.md), [SMI](../smi/index.md), [IXS](../ixs/index.md), [SST](../sst/index.md), and [ISS](../iss/index.md), and CORA's second macromolecular-crystallography beamline after Diamond [i03](../i03/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the `NSLS2/fmx-profile-collection` bluesky / ophyd startup files; the MX acquisition logic lives in the `lsdc` / `mxtools` libraries) and verified against it; the goniometer / robot / detector vendor identities and the crystal cut are not in it, so they, and every read value, are carried `confirm` until FMX staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: the second MX, pure reuse

FMX is CORA's first **NSLS-II** macromolecular crystallography beamline and its second MX deployment overall, after Diamond i03. Its value is **coverage and reinforcement**, not a graduation: FMX coins no new Family and graduates nothing. It reuses the MX vocabulary i03 established, the graduated `Goniometer` (the single-omega micro-goniometer with x/y/z centring), the `Camera` (the Eiger pixel detector), the graduated `Transfocator` (the CRL), the `Monochromator`, the `Mirror` (the HFM and the KB microfocus pair), and the robot-as-Positioner pattern, at a second, independent facility. It brings the three MX Methods (rotation `mx_data_collection`, `grid_scan`, `sample_exchange`) to their second consumer, which strengthens but does not coin them (they stay pending, the `energy_scan` deferral discipline). The genuinely non-obvious part of MX, the autonomous sample-exchange loop, is the modelling target it shares with i03: a Procedure over the spine threaded through a `Subject` custody lifecycle and gated by a Clearance.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the shared IVU21 undulator, the front-end and photon shutters, and the high-heat-load slit, then the optics, the horizontal double-crystal monochromator, the focusing mirrors (HFM + the KB pair), the CRL transfocator, the beam-conditioning attenuators, and the slits.
- [Sample](equipment/sample.md): the micro-goniometer, the automated sample-changing robot, the on-axis viewing and illumination, and the sample cooling.
- [Detector](equipment/detector.md): the Eiger area detector, the Mercury fluorescence detector for edge selection, the beamstop, and the beam-position and flux monitors.

Cutting across all three:

- [Controls](equipment/controls.md): the rotation vector controller, the Zebra trigger box, and the LSDC / mxtools acquisition seam.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the rotation data collection, grid scan, and autonomous sample exchange FMX runs, and why their Methods stay pending.

## Governance

[Governance](governance.md): who may act at FMX and the trust shape CORA applies; CORA brings its own per-Actor authority, and the autonomous robot loop is gated by a Clearance.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's FMX content lives, and why FMX graduates nothing.
