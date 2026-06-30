# CHX

*Coherent hard X-ray scattering at NSLS-II, beamline 11-ID: an X-ray photon correlation spectroscopy (XPCS) and small-angle-scattering beamline. This page describes how CORA would model and run CHX; the model is reverse-engineered from public configuration, not yet confirmed by CHX staff.*

| Property | Value |
| --- | --- |
| Asset | `CHX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 11` (PV namespace `XF:11ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | IVU20 in-vacuum undulator (`SR:C11-ID:G1{IVU20:1}`) |

!!! note "How CORA would land on CHX"
    These pages describe how CORA would model, govern, and conduct CHX, the sixth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), and [SIX](../six/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the [`NSLS2/chx-profile-collection`](https://github.com/NSLS2/chx-profile-collection) profile collection) and verified against it; vendor part numbers and physical positions are not in it, so they, and every read value, are carried `confirm` until CHX staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: coherence, a second time

CHX is the **second coherent beamline** CORA models. APS [8-ID](../8-id/index.md) brought XPCS first; CHX brings it at a second facility. The value to CORA is reinforcement: the coherent-beamline shape (an area detector recording a speckle time series under a fast-gated exposure) ports across facilities with no new vocabulary. CHX introduces no new catalog Family, and its techniques sit on the same deferred Methods 8-ID left pending.

XPCS measures the time correlations of a coherent speckle pattern to probe how a sample evolves, so it records long, fast time series on an area detector under a precisely gated exposure. CHX also runs static small- and wide-angle scattering (SAXS/WAXS) and grazing-incidence scattering (GISAXS) on the same detectors.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the IVU20 undulator and the optics hutch (`11-ID-A`), rendered as the generated source-stage device walk: the silicon and multilayer monochromators, the horizontal-deflecting mirror, the compound-refractive-lens transfocator, and the pink/mono-beam slits.
- [Sample](equipment/sample.md): the endstation beam-defining and guard slits that condition the coherent beam, the grazing-incidence mirror for GISAXS, the sample stack positioned in the coherent focus, and the sample-environment thermal stage.
- [Detector](equipment/detector.md): the coherent area detectors that record the speckle time series, the SAXS detector positioner and beamstop, the flux counter, and the occasional fluorescence detector.

Cutting across all three:

- [Controls](equipment/controls.md): the Zebra trigger that gates the fast shutter and the detector frames for an XPCS time series, and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the coherent-scattering techniques CHX runs (XPCS, SAXS/WAXS, GISAXS), each a [Catalog](../../catalog/methods.md) Method, and why their Methods stay deferred (the 8-ID owner-scope cohort).

## Governance

[Governance](governance.md): who may act at CHX and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's CHX content lives.
