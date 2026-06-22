# The beamline

*The TomoWISE beamline as five areas you can jump to: the three stations the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stations**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that places the specimen in it, and the [Detector](detector.md) that records what comes through. Cutting across all three are the two shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated hutches contain it: an optics hutch (sources, front end, optics) and an experiment hutch (both endstations and the detector).

The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right. So the list reads as one row of peers, but the first three share an axis the last two cross.

## Stations

- [Source](../beamline.md): the shared beam delivery. Two switchable insertion devices (CPMU14 undulator, 3T3PW wiggler) feed a front end of masks and a heat absorber, then an optics hutch of filters and a multilayer monochromator (MLM), then the safety shutters. The operation mode selects source, filters, and whether the MLM and KB optics are in the beam.
- [Sample](sample.md): the sample stage, two stations sharing the detector. The microtomography station (~45 m) carries the rotary stage, sample positioning, laminography tilt, sample-side slits and fast shutter, and a slip ring; the nanotomography station (~49 m) adds the KB mirror pair and a six-axis sample manipulator on a granite support.
- [Detector](detector.md): one gantry on 7 m floor rails serves both stations (45 m to the 52 m hutch wall), carrying interchangeable microscopes (MicLFOV, MicHR) composed as the `Microscope` Assembly, and four shared cameras.

## Shared

- [Controls](controls.md): the MAX IV Tango/Sardana control stack and the rotary-stage-master trigger scheme.
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum); carried in the descriptor, with no operations page yet in this design phase.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, target Models, and pending confirmations). The hutch PSS permit signals are MAX IV facility signals, not yet named (see [Open questions](../questions.md)).
