# The beamline

*The part of SIX CORA models today, as areas you can jump to: the optics and monochromator spine, the UHV RIXS sample, and the spectrometer, plus the controls. First cut.*

SIX is the NSLS-II RIXS beamline at sector 2-ID, and CORA's first soft X-ray deployment. Its PV zones run `XF:02IDA` (front-end optics), `XF:02IDB` (the plane-grating monochromator), `XF:02IDC` (refocusing optics + exit slit), and `XF:02IDD-ES` (the RIXS endstation). This cut models the operational core across them; the legacy end-station monochromator and the simulated devices are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the beam, the [Sample](sample.md) that places the specimen under UHV at a chosen temperature and angle, and the [Detector](detector.md) that disperses and records the scattered light. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the EPU, the front-end mirror M1 and slit and the polarization diagnostic, the plane-grating monochromator and its slits, and the M3/M4 refocusing optics with the resolution-defining exit slit.
- [Sample](sample.md): the UHV cryostat sample manipulator, the sample chamber, the endstation mirrors M5/M6, and the sample temperature controller.
- [Detector](detector.md): the energy-dispersive RIXS spectrometer arm, the photon-counting RIXS camera, and the counting electronics.

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, and the bluesky-plan / queue-server orchestration CORA's edge replaces. The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum for the UHV optics and chambers; cryogens for the manipulator); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including which loose families are held at n=1.
