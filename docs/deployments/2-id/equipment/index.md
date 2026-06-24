# The beamline

*The part of 2-ID CORA models today, as areas you can jump to: the source spine and the 2-ID-D microprobe endstation, plus the controls that drive them. Design-phase.*

2-ID is the Sector 2 hard X-ray microprobe beamline: one insertion-device source feeding more than one experiment hutch. This scaffold models the `2-ID-D` hutch, the scanning fluorescence microprobe, and the source optics it draws on. The sister station(s) and the upstream optics-hutch detail are deferred and flagged `TOPO-1` (see [Model](../model.md#deliberately-not-here-yet)), the same way the 32-ID scaffold modelled only 32-ID-C.

The modelled beamline divides into two kinds of thing. Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and focuses the beam, the [Sample](sample.md) stage that rasters the specimen through the focused spot, and the [Detector](detector.md) that records the fluorescence at each point. Cutting across them are the [Controls](controls.md) that drive the hardware. The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the Sector 2 undulator and the monochromator that selects the scanning energy (both upstream and shared across the sector), then the Fresnel zone plate in 2-ID-D that focuses the beam to the scanning spot. The zone plate carries the `zp_z` focus axis EAA's autofocus loop drives. Whether the source optics serve more than one hutch is the open `TOPO-1` question.
- [Sample](sample.md): the sample-scanning stack in `2-ID-D`, the raster axes the sample moves through the focused spot on (a 2D fly raster or a 1D step scan).
- [Detector](detector.md): the energy-dispersive fluorescence detector that records an X-ray spectrum at each scan point, from which element maps are fit downstream.

## Shared

- [Controls](controls.md): the APS EPICS control stack and the Bluesky scan path, and the autofocus and drift-correction loop CORA's Conductor takes over from EAA. Device handles are not yet on file (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water); carried in the descriptor, with no operations page yet in this design phase.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model for the modelled part (every device by `parent_id`, with Families and pending confirmations). The hutch PSS permit signal is an APS facility signal, not yet named (see [Open questions](../questions.md)).
