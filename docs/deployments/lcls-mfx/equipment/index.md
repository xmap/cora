# The beamline

*The MFX beamline as four areas you can jump to: the three stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the three **stages**: the [Source](../beamline.md) that delivers and conditions the beam, the [Optics and endstation](optics.md) stage where the beam is focused and meets the sample, and the [Detector](detector.md) that records each shot. Cutting across all three are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated zones contain it: a shared front-end / transport zone (the FEL source, solid attenuators, offset and transport mirrors, the PPS stopper, transport diagnostics) and the MFX experiment hutch (conditioning optics, sample delivery, spectrometer, detector). `pcdshub` records which beamline-line zone each device is in, but not which access-gated hutch or its safety meaning (ENC-1).

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways; and a resource is a Supply in its own right.

## Stages

- [Source](../beamline.md): the FEL source and its pulse-energy gas detector, then the shared front end and X-ray transport. The transport mirrors are where one source is steered to one instrument at a time, the switched-source seam (TOPO-1).
- [Optics and endstation](optics.md): the MFX hutch. The pulse picker, solid-Si attenuator, diamond channel-cut mono, focusing lenses (transfocator + prefocus), slits, and per-shot diagnostics condition the beam; the pump-probe laser, the liquid-jet sample delivery, and the von Hamos emission spectrometer sit at the interaction point.
- [Detector](detector.md): the per-shot area detector, read not by a poll loop but by the event-driven DAQ.

## Shared

- [Controls](controls.md): the `pcdshub` EPICS stack (with the real PV prefixes), the EventSequencer beam-synchronous timing, and the event-driven DAQ that CORA references but does not own.
- Resources: the continuously-available supplies a run needs (the FEL photon beam, cooling water, vacuum); carried in the descriptor, with no operations page in this design phase. The FEL beam is a shared, switched resource (TOPO-1).

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the `pcdshub` control handles, and pending confirmations).
- [Model](../model.md): the architectural gap register, the real product of this XFEL exercise.
