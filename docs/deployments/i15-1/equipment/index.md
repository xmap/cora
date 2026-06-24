# The beamline

*The I15-1 beamline as the three stages the beam passes through, plus the controls that drive them. Design-phase.*

Along the beam, in order, sit the three **stages**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that places the specimen, and the [Detector](detector.md) that records the scattering. Cutting across all three are the [Controls](controls.md). Two access-gated hutches contain it: an optics hutch (the monochromator, mirror, attenuators, slits) and an experiment hutch (the sample environment, the two-theta arm, and the detectors). dodal records which functional zone each device is in, but not which hutch (ENC-1); it does record real interlock PVs, carried as the Enclosure permit-signal candidates (PSS-1, INTERLOCK-1).

## Stages

- [Source](../beamline.md): the beam delivery and conditioning. The bent-Laue monochromator (a fixed-energy selection, a y-to-energy lookup readback, not a scanning DCM), the multilayer mirror, the attenuators, the beam-defining slits, the beamstop, and the safety and fast shutters.
- [Sample](sample.md): the experiment hutch. The sample translation and hexapod, the two-theta detector arm, the interchangeable sample-environment devices on a shared rail (blower / cobra / cryostream), and the powder/capillary sample-changing robot.
- [Detector](detector.md): the Eiger area detector capturing wide-Q total-scattering frames, a second detector translation, and the incident-flux monitor.

## Shared

- [Controls](controls.md): the Diamond EPICS control stack (with the real dodal PV handles) and the Zebra FPGA timing.
- Resources: the continuously-available supplies (photon beam, cooling water, vacuum); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the dodal control handles, and pending confirmations). The PSS / gonio interlocks are carried as the Enclosure permit, not as devices (INTERLOCK-1).
