# The beamline

*The 19-BM-FACT beamline as areas you can jump to: the stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the stages: the [Source](../beamline.md) that delivers and conditions the beam in the front-end optics enclosure, the [Sample](sample.md) stage in air at the endstation, and the [Detector](detector.md) that records what comes through. Cutting across all of them are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on.

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right.

## Enclosures

19-BM-FACT runs in **filtered white-beam mode only**, with beam present in all enclosures whenever the front-end shutter is open. Three access-gated volumes contain it:

| Enclosure | Role | What is in it |
| --- | --- | --- |
| `19-BM-A` | Front-end optics (FOE) | exit mask, bremsstrahlung collimators, white-beam slits, the F3-30 filter unit, the gate valve, UHV transport |
| `19-BM-C` | Transport | shielded UHV transport only; the beam passes through entirely in vacuum, no intercepts, so no Device Assets are registered here |
| `19-BM-D` | Endstation | the Be and Kapton windows, the in-air sample stage, the indirect-detection imaging system, and the downstream beam stops |

19-BM-C and 19-BM-D share a downstream-wall guillotine that is held open during operation, so they act as a single shielded volume from a radiation-safety perspective. Whether CORA models them as one Enclosure or two coupled ones is an [open question](../questions.md) (ENC-1).

## Stages

- [Source](../beamline.md): the bending-magnet beam delivery and conditioning. There is no monochromator and no mirror optics, so the spectrum is set entirely by the F3-30 filter unit, not by optic moves.
- [Sample](sample.md): the in-air endstation. The beamline vacuum terminates at a water-cooled Be window; a Kapton window transitions to air, where the rotary and positioning stages place the specimen in the white beam. The stage is designed to host a robotic sample changer for autonomous operation.
- [Detector](detector.md): the indirect-detection imaging system (scintillator, microscope optics, camera) downstream of the sample, plus the photon and bremsstrahlung stops at the downstream wall.

## Shared

- [Controls](controls.md): the EPICS control stack and the high-throughput trigger scheme.
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum); carried in the descriptor, with no operations page yet in this design phase.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and the values pending confirmation). The PSS permit signals are APS facility signals, not yet named (see [Open questions](../questions.md)).
