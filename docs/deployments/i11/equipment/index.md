# The beamline

*The I11 beamline as the three stages the beam passes through, plus the controls that drive them. Design-phase.*

Along the beam, in order, sit the three **stages**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage (the diffractometer, the thermal sample environment, and the robot), and the [Detector](detector.md). Cutting across all three are the [Controls](controls.md). Two access-gated hutches contain it: an optics hutch (the monochromator, slits) and an experiment hutch (the diffractometer, sample environment, robot, and detector). dodal records which functional zone each device is in, but not which hutch (ENC-1).

## Stages

- [Source](../beamline.md): the storage-ring state, the double-crystal monochromator, and the beam-defining slits.
- [Sample](sample.md): the powder diffractometer (sample rotation + detector-arm angles), the capillary spinner for powder averaging, the four thermal actuators (the variable-temperature environment that earns the TemperatureController abstraction), and the sample-changing robot + carousel.
- [Detector](detector.md): the Mythen3 position-sensitive strip detector.

## Shared

- [Controls](controls.md): the Diamond EPICS control stack (with the real dodal PV handles).
- Resources: the continuously-available supplies (photon beam, cooling water, vacuum); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the dodal control handles, and pending confirmations). The TemperatureController graduation + settable-actuator Role earn landed via a separate gate-reviewed change (TEMP-1): it is now a catalog Family presenting `Regulator`.
