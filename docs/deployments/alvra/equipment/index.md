# The beamline

*The Alvra station as the areas you can jump to: the stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the **stages**: the [Source](../beamline.md) that delivers and conditions the beam (the Aramis FEL source, the front end, and the Aramis optics hutch), the [Endstation](endstation.md) where the focused beam meets the sample, and the [Detector](detector.md) that records each shot. Cutting across them are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated zones contain it: a shared Aramis optics hutch (the offset mirrors, the double-crystal mono, the pulse picker, the attenuator, the KB focusing mirrors, the timing diagnostics) and the Alvra experiment hutch (the Prime endstation, the pump-probe laser, the von Hamos spectrometer, the detector). `eco` records which beamline-line zone each device is in (`SARFE10`, `SAROP11`, `SARES11`), but not which access-gated hutch or its safety meaning (ENC-1).

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways; and a resource is a Supply in its own right.

## Stages

- [Source](../beamline.md): the Aramis FEL source and its front-end intensity monitors, then the front-end shutters, slit, and attenuator, and the Aramis optics hutch. The shared Aramis source is steered to one station at a time, the switched-source seam (TOPO-1).
- [Endstation](endstation.md): the Alvra Prime endstation. The Huber sample manipulator, the optical table, and the sample-view microscope position the sample; the pump-probe laser excites it; the von Hamos emission spectrometer measures the emitted X-rays.
- [Detector](detector.md): the per-shot Jungfrau area detector, read not by a poll loop but by the SwissFEL event-driven DAQ.

## Shared

- [Controls](controls.md): the `eco` EPICS device library (with the real PV prefixes), the SwissFEL event-system timing, and the event-driven DAQ that CORA references but does not own.
- Resources: the continuously-available supplies a run needs (the SwissFEL photon beam, cooling water, vacuum); carried in the descriptor, with no operations page in this design phase. The FEL beam is a shared, switched resource (TOPO-1).

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the `eco` control handles, and pending confirmations).
- [Model](../model.md): the architectural gap register, the real product of this second-XFEL exercise.
