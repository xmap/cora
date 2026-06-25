# SRX

*Submicron-resolution X-ray spectroscopy at NSLS-II, beamline 5-ID: a multi-technique hard X-ray microprobe (XRF mapping, XANES, XRF-tomography, diffraction, imaging). This page describes how CORA would model and run SRX; the model is reverse-engineered from public configuration, not yet confirmed by SRX staff.*

| Property | Value |
| --- | --- |
| Asset | `SRX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 5` (PV namespace `XF:05ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | IVU21 in-vacuum undulator (`SR:C5-ID:G1{IVU21:1}`) |

!!! note "How CORA would land on SRX"
    These pages describe how CORA would model, govern, and conduct SRX, the fourth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), and [BMM](../bmm/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the [`NSLS2/srx-profile-collection`](https://github.com/NSLS2/srx-profile-collection) profile collection) and verified against it; vendor part numbers and physical positions are not in it, so they, and every read value, are carried `confirm` until SRX staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: many techniques, one instrument

The earlier deployments each anchor one technique family (FXI full-field imaging, HXN scanning ptychography, BMM spectroscopy). SRX is the first that runs **several on one beamline**: scanning XRF mapping, XANES, XRF-tomography, diffraction (via pixel detectors), and full-field imaging, across a micro endstation and a KB-focused nano endstation. The value to CORA is breadth, exercising the **multi-Capability-per-beamline** shape, and reuse: SRX introduces no new device Family, binding the ones the earlier NSLS-II beamlines and the catalog already carry.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the IVU21 undulator and the optics hutch (`5-ID-A`), rendered as the generated source-stage device walk: the high-heat-load monochromator, the focusing mirror, and the white/pink-beam and secondary-source slits.
- [Sample](equipment/sample.md): the KB nanofocus optics and the nano-endstation sample stack rastered through the focused spot, with the attenuators and sample-environment thermal control.
- [Detector](equipment/detector.md): the detector set that selects the technique, the fluorescence spectrometer (XRF/XANES), the pixel detectors (diffraction), the imaging camera, and the flux counters.

Cutting across all three:

- [Controls](equipment/controls.md): the Zebra position-capture trigger for fly XRF mapping and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the several techniques SRX runs, each a [Catalog](../../catalog/methods.md) Method bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here), and the multi-Capability-per-beamline shape they exercise.

## Governance

[Governance](governance.md): who may act at SRX and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's SRX content lives.
