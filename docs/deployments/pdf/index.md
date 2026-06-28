# PDF

*Pair distribution function and total scattering at NSLS-II, beamline 28-ID-1: a high-energy beam through a powder or capillary sample onto flat-panel and pixel area detectors, with a near and a far detector distance merged to reach the high Q a PDF needs. This page describes how CORA would model and run PDF; the model is reverse-engineered from public configuration, not yet confirmed by PDF staff.*

| Property | Value |
| --- | --- |
| Asset | `PDF` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 28` (PV namespace `XF:28ID1*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | Shared 28-ID damping wiggler (inferred; no source PV in config) |

!!! note "How CORA would land on PDF"
    PDF (28-ID-1) and [XPD](../xpd/index.md) (28-ID-2) are the two endstations on the shared 28-ID damping wiggler: the same science family (high-energy powder diffraction and total scattering / PDF), different branch and PV namespace. These pages describe how CORA would model, govern, and conduct PDF, the dedicated total-scattering endstation, reusing XPD's modelling wholesale. They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the [`NSLS2/pdf-profile-collection`](https://github.com/NSLS2/pdf-profile-collection) profile collection and the [`NSLS2/pdftools`](https://github.com/NSLS2/pdftools) device library) and verified against them; vendor part numbers and physical positions are not in them, so they, and every read value, are carried `confirm` until PDF staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: total scattering at a second endstation

PDF is the **twin of XPD** on the shared 28-ID damping wiggler, and through XPD the NSLS-II counterpart of Diamond [i11](../i11/index.md) (powder diffraction) and [i15-1](../i15-1/index.md) (total scattering / PDF). Its value to CORA is reinforcement: the high-energy powder / PDF shape, a high-flux beam onto a large flat-panel detector with the detector distance setting the accessible Q, ports to a second NSLS-II endstation with no new vocabulary. PDF introduces **no new catalog Family**, and its techniques sit on the same deferred Methods XPD and the Diamond beamlines leave pending.

Two things distinguish PDF from XPD, and CORA carries both by what is real rather than coining anything new:

- A **side-bounce monochromator** (a single-bounce Laue crystal) in place of XPD's bent double-Laue. Both are high-energy Laue monochromators, so this is a `Monochromator` settings difference, not a new Family.
- An explicit **two-detector, two-distance** acquisition: a near panel and a far panel, one static and one stepping in and out of the beam, merged to cover the wide Q-range a pair distribution function needs. XPD reaches the two distances by moving one detector; PDF carries two (DIST-1).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the shared 28-ID damping wiggler and the optics hutch (`28-ID-1-A`), rendered as the generated source-stage device walk: the side-bounce monochromator, the vertical focusing mirror, the white-beam slit, and the master energy.
- [Sample](equipment/sample.md): the endstation cleanup slit, the fast shutter, the capillary spinner, the sample-environment stage, and the thermal-environment cluster (cryostream, cryostat, furnace).
- [Detector](equipment/detector.md): the PerkinElmer flat-panel and Pilatus pixel area detectors, the two detector towers that set the near and far distances, the beamstops, and the flux monitor.

Cutting across all three:

- [Controls](equipment/controls.md): the software-triggered acquisition (no hardware timing box, as at XPD), the two-detector plan that sequences the two distances, and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the total-scattering and powder-diffraction techniques PDF runs, each a [Catalog](../../catalog/methods.md) Method, and why their Methods stay deferred (the i11 / i15-1 / XPD owner-scope cohort).

## Governance

[Governance](governance.md): who may act at PDF and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's PDF content lives.
