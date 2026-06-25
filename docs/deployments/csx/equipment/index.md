# The beamline

*The part of CSX CORA models today, as areas you can jump to: the optics and monochromator spine, the TARDIS diffractometer sample, and the coherent detectors, plus the controls. First cut.*

CSX is the NSLS-II coherent soft X-ray scattering beamline on the inboard 23-ID-1 branch. Its PV zones run `XF:23IDA` (front-end optics), `XF:23ID1-OP` (the branch optics, the VLS-PGM), and `XF:23ID1-ES` (the TARDIS endstation). This cut models the operational core across them; the fine piezo nanopositioner and the simulated devices are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the beam, the [Sample](sample.md) that orients the specimen on the TARDIS diffractometer, and the [Detector](detector.md) that records the coherent scattering. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the two canted EPUs, the front-end mirror, the VLS-PGM, the refocusing mirror M3A, and the branch slits.
- [Sample](sample.md): the TARDIS E6C diffractometer with its reciprocal-space coordination, the sample stage and holography stage, and the cryostat temperature controller.
- [Detector](detector.md): the FastCCD and AXIS coherent area detectors, the fast shutter and diode, and the counting electronics.

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, and the bluesky-plan / queue-server orchestration CORA's edge replaces. The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum for the UHV optics and in-vacuum endstation; cryogens for the cryostat); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations). CSX adds no new family; it graduates `GratingMonochromator` and reuses the Diffractometer Assembly.
