# The beamline

*The I24 beamline as four areas you can jump to: the three stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stages**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that holds the fixed-target chip in it, and the [Detector](detector.md) that records each diffraction snapshot. Cutting across all three are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated hutches contain it: an optics hutch (the monochromator, focusing mirrors, attenuator, aperture) and an experiment hutch (the goniometer, the chip stage, the sample environment, and the detector). dodal records which functional zone each device is in, but not which hutch or its safety meaning (ENC-1, PSS-1).

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right.

## Stages

- [Source](../beamline.md): the beam delivery and conditioning. The undulator feeds the double-crystal monochromator and the focusing mirrors (with a selectable focus mode), through the filter-based attenuator and the beam-defining aperture; the machine source state is observed, not driven. The undulator gap is not a dodal device here (SRC-1).
- [Sample](sample.md): the experiment hutch. The vertical pin goniometer (which reuses the Goniometer Family I03 graduated), the fixed-target chip stage (the PMAC XYZ `LinearStage` that rasters the addressable chip across the beam), the dual backlight, the on-axis-view alignment camera, the positioned beamstop, and the fast Zebra-controlled sample shutter. There is no rotation sweep and no sample-changing robot: a window of the chip is set, a single snapshot is taken, and the stage steps on.
- [Detector](detector.md): the Eiger area detector on its translation stage as the production path, with the Jungfrau carried as commissioning (DET-1), and the Zebra timing that hardware-sequences the chip-raster collection.

## Shared

- [Controls](controls.md): the Diamond EPICS / ophyd-async control stack (with the real dodal PV handles) and the Zebra FPGA timing and triggering. The serial collection (the PMAC chip-raster motion program, the encoder position-compare, the laser triggers, the Zebra TTL gating) is the orchestration CORA's edge replaces (SSX-1).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum on the optics path); carried in the descriptor, with no operations page in this design phase (SUP-1).

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the dodal control handles, and pending confirmations). The hutch PSS permit signals are Diamond facility signals, not in dodal (see [Open questions](../questions.md)).
