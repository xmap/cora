# SST

*Spectroscopy Soft and Tender at NSLS-II, beamline 7-ID: a dual-branch, multi-endstation beamline spanning soft X-ray scattering (RSoXS), absorption (NEXAFS), and photoemission (HAXPES). This page describes how CORA would model and run SST; the model is reverse-engineered from public configuration, not yet confirmed by SST staff.*

| Property | Value |
| --- | --- |
| Asset | `SST` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 7` (PV namespace `XF:07ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | two insertion devices: soft EPU60 (`SR:C07-ID:G1A{SST1:1}`) + tender U42 (`SR:C07-ID:G1A{SST2:1}`) |

!!! note "How CORA would land on SST"
    These pages describe how CORA would model, govern, and conduct SST, the twelfth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), [SIX](../six/index.md), [CHX](../chx/index.md), [CSX](../csx/index.md), [XPD](../xpd/index.md), [ESM](../esm/index.md), [SMI](../smi/index.md), and [IXS](../ixs/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the `NSLS2/sst-*-profile-collection` endstation repos and the shared `NSLS-II-SST/sst-base` package) and verified against it; vendor part numbers and physical positions are not in it, so they, and every read value, are carried `confirm` until SST staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: two branches, many techniques, one beamline

SST is the broadest NSLS-II beamline CORA models: **two source-and-monochromator branches** (a soft branch, an EPU60 undulator with a plane-grating monochromator; a tender branch, a U42 undulator with a double-crystal monochromator) feeding **several endstations** across three technique families, soft X-ray scattering (RSoXS), absorption spectroscopy (NEXAFS), and photoemission (HAXPES). The value to CORA is breadth at the Site level: it reuses the soft-X-ray vocabulary the earlier NSLS-II beamlines earned (the `GratingMonochromator`, the `Manipulator`, the `ElectronAnalyzer`) across one more, larger instrument, and it brings the `ElectronAnalyzer` family to its second sighting, which GRADUATED it into the catalog. SST coins no new catalog Family of its own.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the two branch undulators (soft EPU60, tender U42) and the front-end shutter, then the optics, the soft plane-grating and tender double-crystal monochromators, the mirrors, and the slits.
- [Sample](equipment/sample.md): the soft (RSoXS) and tender (HAXPES) sample manipulators, and the thermal environment.
- [Detector](equipment/detector.md): the detectors that make SST multi-technique, the soft-scattering CCD, the hemispherical electron analyzer, the microcalorimeter, and the flux monitors.

Cutting across all three:

- [Controls](equipment/controls.md): the fast shutter that gates the exposure, the branch-selection, and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the soft-scattering, absorption, and photoemission techniques SST runs, and why their Capabilities stay deferred.

## Governance

[Governance](governance.md): who may act at SST and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's SST content lives, and the `ElectronAnalyzer` graduation it earned.
