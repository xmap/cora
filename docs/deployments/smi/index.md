# SMI

*Soft Matter Interfaces at NSLS-II, beamline 12-ID: a small- and wide-angle scattering beamline (SAXS / WAXS) with grazing-incidence (GISAXS / GIWAXS) and in-situ soft-matter cells. This page describes how CORA would model and run SMI; the model is reverse-engineered from public configuration, not yet confirmed by SMI staff.*

| Property | Value |
| --- | --- |
| Asset | `SMI` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 12` (PV namespace `XF:12ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | in-vacuum undulator (`SR:C12-ID:G1{IVU:1}`) |

!!! note "How CORA would land on SMI"
    These pages describe how CORA would model, govern, and conduct SMI, the tenth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), [SIX](../six/index.md), [CHX](../chx/index.md), [CSX](../csx/index.md), [XPD](../xpd/index.md), and [ESM](../esm/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the [`NSLS2/smi-profile-collection`](https://github.com/NSLS2/smi-profile-collection) profile collection) and verified against it; vendor part numbers and physical positions are not in it, so they, and every read value, are carried `confirm` until SMI staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: scattering, a second facility, plus grazing incidence

SMI is the NSLS-II twin of the Diamond [I22](../i22/index.md) (SAXS / WAXS) beamline. It brings that scattering axis to a second facility, and it adds two things i22 does not foreground: **grazing-incidence** scattering (GISAXS / GIWAXS) off films and interfaces, and a rich set of **in-situ soft-matter cells**. The value to CORA is reinforcement: the scattering shape (two area detectors read at once, the detector distance setting the accessible Q) ports across facilities with no new vocabulary, and the grazing-incidence geometry is a sample-orientation variant, not a new device family.

A scattering measurement reads the SAXS and WAXS Pilatus detectors simultaneously: the SAXS 2M down an in-vacuum flight path for low Q, the WAXS 900KW on a swing arc for wide Q. SMI introduces no new catalog Family, and its techniques sit on the same deferred Capabilities i22 left pending.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the in-vacuum undulator and the front-end shutter, then the optics, the double-crystal monochromator, the horizontal and vertical focusing mirrors, the compound-refractive-lens transfocator, and the slits and attenuators.
- [Sample](equipment/sample.md): the HUB sample stack with grazing-incidence axes, and the Linkam sample environment.
- [Detector](equipment/detector.md): the simultaneous SAXS and WAXS Pilatus detectors, the camera-length stage and beamstops, the flux monitor, and the fluorescence detector.

Cutting across all three:

- [Controls](equipment/controls.md): the fast shutter that gates the exposure, and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the scattering techniques SMI runs (SAXS, WAXS, GISAXS, GIWAXS), and why their Capabilities stay deferred (the i22 owner-scope cohort).

## Governance

[Governance](governance.md): who may act at SMI and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's SMI content lives.
