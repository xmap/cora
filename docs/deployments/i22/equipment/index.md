# The beamline

*The I22 beamline as four areas you can jump to: the three stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stages**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that places the specimen in it, and the [Detector](detector.md) that records what scatters. Cutting across all three are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated hutches contain it: an optics hutch (the monochromator, mirrors, transfocator, slits) and an experiment hutch (the sample environment and the detectors). dodal records which functional zone each device is in, but not which hutch or its safety meaning (ENC-1).

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right.

## Stages

- [Source](../beamline.md): the beam delivery and conditioning. The undulator feeds the double-crystal monochromator and the KB focusing mirror pair (with adaptive bimorph correction) and the compound-refractive-lens transfocator, through the beam-defining slits. The machine-level storage-ring state is observe-only.
- [Sample](sample.md): the experiment hutch. The sample base and on-axis-view alignment camera, the incident and transmitted flux monitors, and the sample-environment actuators (temperature, flow).
- [Detector](detector.md): two area detectors, not one. A SAXS detector at long camera length and a WAXS detector at short camera length, read simultaneously, with the beamstops that protect them.

## Shared

- [Controls](controls.md): the Diamond EPICS control stack (with the real dodal PV handles) and the PandABox FPGA timing and triggering.
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum); carried in the descriptor, with no operations page in this design phase.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the dodal control handles, and pending confirmations). The hutch PSS permit signals are Diamond facility signals, not in dodal (see [Open questions](../questions.md)).
