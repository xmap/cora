# The beamline

*The part of 32-ID CORA models today, as areas you can jump to: the source spine and the TXM endstation, plus the controls that drive them. Design-phase.*

32-ID is a canted beamline with three lead-shielded stations: `32-ID-A` (optics only), `32-ID-B` (white-beam high-speed imaging and the additive-manufacturing rig), and `32-ID-C` (the transmission X-ray microscope). This scaffold models the `32-ID-A` optics spine and the `32-ID-C` TXM endstation; `32-ID-B`'s instruments and the projection microscope are deferred (see [Model](../model.md#deliberately-not-here-yet)).

The modelled beamline divides into two kinds of thing. Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that places the specimen in it, and the [Detector](detector.md) that records what comes through. Cutting across them are the [Controls](controls.md) that drive the hardware. The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the shared `32-ID-A` optics spine. A canted pair of planar undulators feeds a front end of a beam-defining mask, a window, and the JJ X-Ray white-beam slits, then the Si(111) monochromator and the P4-50 mode shutter that selects white-beam or monochromatic operation, then the PSS safety shutter into the experimental hutches. Whether this spine is shared by both branches or duplicated per branch is the open `TOPO-1` question.
- [Sample](sample.md): the TXM sample stage in `32-ID-C`, a granite-supported rotation axis with the zone-plate optics (condenser, objective zone plate, phase ring) that magnify the transmitted beam.
- [Detector](detector.md): the TXM indirect-detection chain, a scintillator, microscope objective, and camera on a granite detector support.

## Shared

- [Controls](controls.md): the APS EPICS control stack and the remote-access path. Device handles are not yet on file (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum); carried in the descriptor, with no operations page yet in this design phase.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model for the modelled part (every device by `parent_id`, with Families and pending confirmations). The hutch PSS permit signals are APS facility signals, not yet named (see [Open questions](../questions.md)).
