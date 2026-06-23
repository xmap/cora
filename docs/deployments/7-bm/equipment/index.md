# The beamline

*The 7-BM beamline as four areas you can jump to: the three stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stages**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that places the specimen in it, and the [Detector](detector.md) that records what comes through. Cutting across all three are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated hutches contain it: an optics hutch (7-BM-A: filters, chopper, monochromator, mirrors) and an experiment hutch (7-BM-B: the sample environment and the detectors).

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right. So the list reads as one row of peers, but the first three share an axis the last two cross.

## Stages

- [Source](../beamline.md): the beam delivery and conditioning. The source feeds the front-end station shutter, then the beam-conditioning optics (the water-cooled filters, the rotary chopper that reduces white-beam duty cycle, the white-beam slits), then the energy-selecting and focusing optics (the double multilayer monochromator, the multilayer mirror, the KB focusing pair), then the safety shutter into the experiment hutch. The beam mode (white, monochromatic, focused) is selected per technique.
- [Sample](sample.md): the experiment hutch. Tomography rotation and sample positioning, the energy-dispersive gauge slits, and the flow and combustion sample environment (the metered process gases, served by the compressed-air and vacuum plant).
- [Detector](detector.md): the several detector modalities, not the single camera path of the 2-BM micro-CT pilot. An imaging camera (scintillator-coupled) for tomography, a high-speed movie camera, a point photodiode for time-resolved radiography, and a germanium energy-dispersive detector for diffraction.

## Shared

- [Controls](controls.md): the APS EPICS control stack and the DG645 timing and triggering scheme (ring-sync, chopper-to-camera delay, top-up inhibit).
- Resources: the continuously-available supplies a run needs (photon beam, compressed air, vacuum, process gas, cooling water); carried in the descriptor, with no operations page yet in this design phase.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations). The hutch PSS permit signals are APS facility signals, not yet named (see [Open questions](../questions.md)).
