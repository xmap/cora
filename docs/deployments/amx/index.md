# AMX

*Highly Automated Macromolecular Crystallography at NSLS-II, beamline 17-ID-1: high-throughput rotation MX data collection on a single-omega goniometer and an Eiger detector, with an automated EMBL robot sample changer. FMX's sibling on the shared 17-ID straight. This page describes how CORA would model and run AMX; the model is reverse-engineered from public configuration, not yet confirmed by AMX staff.*

| Property | Value |
| --- | --- |
| Asset | `AMX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 17` (PV namespace `XF:17ID*`, the 17-ID-1 branch) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | IVU21 in-vacuum undulator on the NSLS-II 3 GeV ring (shared with FMX on the 17-ID straight) |

!!! note "How CORA would land on AMX"
    These pages describe how CORA would model, govern, and conduct AMX, the seventeenth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), [SIX](../six/index.md), [CHX](../chx/index.md), [CSX](../csx/index.md), [XPD](../xpd/index.md), [ESM](../esm/index.md), [SMI](../smi/index.md), [IXS](../ixs/index.md), [SST](../sst/index.md), [ISS](../iss/index.md), [FMX](../fmx/index.md), [CMS](../cms/index.md), and [XFM](../xfm/index.md), and CORA's third macromolecular-crystallography beamline after Diamond [i03](../i03/index.md) and NSLS-II FMX. They are not a survey of the beamline's current software. The hardware facts are read from public NSLS-II open source (the `NSLS2/amx-profile-collection` bluesky / ophyd startup files; the MX acquisition logic lives in the `lsdc` / `mxtools` libraries) and verified against it; the goniometer / robot / detector vendor identities and the crystal cut are not in it, so they, and every read value, are carried `confirm` until AMX staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: completing the 17-ID MX pair

AMX is FMX's high-throughput sibling: they share the 17-ID straight and the IVU21 undulator, and building AMX completes the NSLS-II MX pair. It is CORA's third MX deployment (after Diamond i03 and NSLS-II FMX) and a **pure-reuse** build: it coins no Family and graduates nothing. It reuses the MX vocabulary i03 and FMX established, the graduated `Goniometer` (the single-omega micro-goniometer), the `Camera` (the Eiger), the `Monochromator` (here a vertical DCM), the `Mirror` (the tandem-deflection and KB pairs), and the robot-as-Positioner pattern. It brings the three MX Methods (rotation `mx_data_collection`, `grid_scan`, `sample_exchange`) to their third consumer, which strengthens but does not coin them (Methods are coined on a conduct-path, not a sighting count). A few hardware differences from FMX show CORA's modelling generalizes: AMX uses a vertical (not horizontal) DCM, tandem-deflection mirrors (not a single horizontal focusing mirror), and has no CRL transfocator.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the shared IVU21 undulator, the front-end and photon shutters, and the high-heat-load slit, then the optics, the vertical double-crystal monochromator, the tandem-deflection and KB mirrors, the beam-conditioning attenuator, and the slits.
- [Sample](equipment/sample.md): the micro-goniometer, the automated EMBL robot, and the on-axis viewing.
- [Detector](equipment/detector.md): the Eiger area detector, the Mercury fluorescence detector for edge selection, the beamstop, and the beam-position and flux monitors.

Cutting across all three:

- [Controls](equipment/controls.md): the Zebra trigger box, the rotation motion, and the LSDC / mxtools acquisition seam.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the rotation data collection, grid scan, and autonomous sample exchange AMX runs, and why their Methods stay pending.

## Governance

[Governance](governance.md): who may act at AMX and the trust shape CORA applies; the autonomous robot loop is gated by a Clearance.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's AMX content lives, and why AMX graduates nothing.
