# The beamline

*The I03 beamline as four areas you can jump to: the three stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stages**: the [Source](../beamline.md) that delivers and conditions the beam, the [Sample](sample.md) stage that orients the crystal in it, and the [Detector](detector.md) that records what diffracts. Cutting across all three are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated hutches contain it: an optics hutch (the monochromator, mirror, filters, slits, diagnostics) and an experiment hutch (the goniometer, robot, sample environment, and detector). dodal records which functional zone each device is in, but not which hutch or its safety meaning (ENC-1).

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right.

## Stages

- [Source](../beamline.md): the beam delivery and conditioning. The undulator feeds the double-crystal monochromator and the focusing mirror (with selectable coatings and a bimorph bend), through the filters, collimation table, beamstop, aperture-scatterguard, and shutters; the beam-position and flux diagnostics watch it. Energy is set by the undulator-DCM coupling, modelled as a Method (ENERGY-1).
- [Sample](sample.md): the experiment hutch. The Smargon goniometer (which graduated the Goniometer Family), the sample-centring base, the automated sample-changing robot, and the sample environment (illumination, cryo-cooling, thawing).
- [Detector](detector.md): the Eiger area detector on its translation, and a retractable fluorescence detector for anomalous / element identification.

## Shared

- [Controls](controls.md): the Diamond EPICS control stack (with the real dodal PV handles) and the Zebra / PandABox FPGA timing and triggering.
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum, liquid nitrogen for the cryostream); carried in the descriptor, with no operations page in this design phase.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the dodal control handles, and pending confirmations). The hutch PSS permit signals are Diamond facility signals, not in dodal (see [Open questions](../questions.md)).
