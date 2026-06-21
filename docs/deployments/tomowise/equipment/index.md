# The beamline

*How TomoWISE's areas relate, as designed.*

TomoWISE delivers one beam to two experiment stations that share a detector. The beam path runs in three stages, the same source / sample / detection spine every CORA beamline inherits.

- [Source](../beamline.md): the shared beam delivery. Two switchable insertion devices (CPMU14 undulator, 3T3PW wiggler) feed a front end of fixed and movable masks and a heat absorber, then an optics hutch of filters (CVD diamond, power-filter and metal-filter units) and a multilayer monochromator (MLM), then the safety shutters. The operation mode selects source, filters, and whether the MLM and KB optics are in the beam.
- [Endstations](endstations.md): two sample stations. The microtomography station (~45 m) carries the rotary stage, sample positioning, laminography tilt, sample-side slits and fast shutter, and a slip ring for continuous rotation. The nanotomography station (~49 m) adds the KB mirror pair for 200-nm-class cone-beam imaging; its sample stage is not yet specified.
- [Detector](detector.md): one gantry on 7 m floor rails serves both stations (45 m to the 52 m hutch wall), carrying interchangeable microscopes (MicLFOV, MicHR) and cameras (four design-target sensors).

Cutting across all three:

- [Controls](controls.md): the MAX IV Tango/Sardana control stack and the rotary-stage-master trigger scheme.

Two access-gated hutches contain the beamline: an optics hutch (sources, front end, optics) and an experiment hutch (both endstations and the detector). Their PSS permit signals are MAX IV facility signals, not yet named (see [Open questions](../questions.md)).

For the full planned device list and the values still pending confirmation, see the [Inventory](../inventory.md).
