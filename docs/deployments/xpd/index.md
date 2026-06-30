# XPD

*X-ray powder diffraction and total scattering at NSLS-II, beamline 28-ID-2: a high-energy powder-diffraction and rapid-acquisition pair-distribution-function (PDF) beamline. This page describes how CORA would model and run XPD; the model is reverse-engineered from public configuration, not yet confirmed by XPD staff.*

| Property | Value |
| --- | --- |
| Asset | `XPD` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 28` (PV namespace `XF:28ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | 28-ID insertion device (no source PV in public config; damping wiggler per facility knowledge, SRC-1) |

!!! note "How CORA would land on XPD"
    These pages describe how CORA would model, govern, and conduct XPD, the eighth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), [SIX](../six/index.md), [CHX](../chx/index.md), and [CSX](../csx/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the [`NSLS2/xpd-profile-collection`](https://github.com/NSLS2/xpd-profile-collection) profile collection) and verified against it; vendor part numbers and physical positions are not in it, so they, and every read value, are carried `confirm` until XPD staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: powder diffraction and PDF, a second facility

XPD is the NSLS-II twin of the Diamond [I11](../i11/index.md) (high-resolution powder diffraction) and [I15-1](../i15-1/index.md) (total scattering / PDF) beamlines. It brings that science axis to a second facility. The value to CORA is reinforcement: the powder-and-PDF shape (a high-energy beam through a powder or capillary sample onto a large area detector, the detector distance setting the accessible Q) ports across facilities with no new vocabulary. XPD introduces no new catalog Family, and its techniques sit on the same deferred Capabilities Diamond left pending.

A PDF measurement captures wide-Q total scattering on a large flat-panel detector at a fixed high energy; the bent double-Laue monochromator and the high-flux insertion-device source deliver the flux and energy that wide-Q reach needs.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the insertion-device source and the optics hutch (`28-ID-A`), rendered as the generated source-stage device walk: the bent double-Laue monochromator, the vertical focusing mirror, the white-beam slit, and the filters.
- [Sample](equipment/sample.md): the diffractometer holding the sample and detector arm, the sample-array stage, the beam-defining pinhole, and the rich sample-environment thermal stages.
- [Detector](equipment/detector.md): the large flat-panel area detectors, the distance stage that sets the accessible Q, the flux counters, and the exposure shutter.

Cutting across all three:

- [Controls](equipment/controls.md): the software-triggered acquisition gated by the exposure shutter, and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the powder-diffraction and total-scattering techniques XPD runs, and why their Capabilities stay deferred (the i11 / i15-1 owner-scope cohort).

## Governance

[Governance](governance.md): who may act at XPD and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's XPD content lives.
