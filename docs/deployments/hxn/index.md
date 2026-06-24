# HXN

*Scanning hard X-ray nanoprobe at NSLS-II, beamline 3-ID: nano-XRF mapping, ptychography, nano-tomography, and spectro-tomography. This page describes how CORA would model and run HXN; the model is reverse-engineered from public configuration, not yet confirmed by HXN staff.*

| Property | Value |
| --- | --- |
| Asset | `HXN` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 3` (PV namespace `XF:03ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | IVU20 in-vacuum undulator (`SR:C3-ID:G1{IVU20:1}`) |

!!! note "How CORA would land on HXN"
    These pages describe how CORA would model, govern, and conduct HXN, the second NSLS-II beamline after [FXI](../fxi/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes, enclosures) are read from public NSLS-II open source (the [`NSLS2/hxn-profile-collection`](https://github.com/NSLS2/hxn-profile-collection) profile collection) and verified against it; vendor part numbers, controller models, and physical positions are not in it, so they, and every read value, are carried `confirm` until HXN staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: a scanning probe

Where [FXI](../fxi/index.md) is a full-field microscope (flood the sample, image the whole field at once), HXN is a **scanning** probe: a zone plate or a multilayer Laue lens focuses the beam to a nano-spot, the sample is rastered through that spot, and several detectors are read at every dwell point, a fluorescence spectrometer for element maps, a pixel detector for ptychography, and flux counters for normalization. The sample position axes *are* the scan. This is the new shape HXN brings to CORA, distinct from every prior full-field or single-shot deployment.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the in-vacuum undulator and the optics hutch (`3-ID-A`), rendered as the generated source-stage device walk: the double-crystal monochromator, three mirrors, and the white-beam slits.
- [Sample](equipment/sample.md): the two focusing optics (zone plate, multilayer Laue lens), their order-sorting apertures and beam stops, and the nano-positioning sample stack rastered through the focus.
- [Detector](equipment/detector.md): the per-point detectors read together during a scan (fluorescence spectrometer, pixel detectors, flux counters).

Cutting across all three:

- [Controls](equipment/controls.md): the Zebra position-capture trigger and the motion controllers (Power PMAC, Attocube ANC350), which HXN exposes in source.

The cross-cutting reference view is the [Inventory](inventory.md): the flat Asset tree by `parent_id` with families, PVs, and the values still pending confirmation.

## Techniques

[Techniques](techniques.md): what HXN would run, each a [Catalog](../../catalog/methods.md) Method bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). The scanning and ptychography Capabilities are deliberately not coined yet (see the page).

## Governance

[Governance](governance.md): who may act at HXN and the trust shape CORA applies. People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's HXN content lives.
