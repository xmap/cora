# The beamline

*The part of 9-ID CORA models today, as areas you can jump to: the optics and focusing spine, the grazing-incidence CSSI sample stack, and the detectors, plus the controls. First cut.*

9-ID is the Coherent Surface Scattering Instrument, with two stations: `9-ID-A` (optics) and `9-ID-D` (the CSSI endstation: focusing, the grazing-incidence sample, and the detectors). This cut models the operational core across both; the metadata / Data Management PVs and the simulated devices are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and focuses the beam, the [Sample](sample.md) stack that places the surface in it at a grazing angle, and the [Detector](detector.md) that records what scatters. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the `9-ID-A` optics (the undulator, the Kohzu monochromator, the FMBO mirrors, the white-beam apertures, and the attenuator) and the `9-ID-D` focusing (the CRL transfocator, the KB mirror) and guard slits.
- [Sample](sample.md): the `9-ID-D` grazing-incidence CSSI sample stack (the sample translation and incidence rotation, the alignment hexapods, and the on-axis viewing microscope).
- [Detector](detector.md): the coherent area detectors (Pilatus, Eiger on a stage), the GIWAXS detector on its pedestal, the beam stop, and the beam-position monitors.

## Shared

- [Controls](controls.md): the APS EPICS control stack, and the metadata / Data Management seam CORA's system of record replaces. The device handles are bound from the beamline's instrument config and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum for the focusing optics and the detector flight); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including which loose families are held for gate-review.
