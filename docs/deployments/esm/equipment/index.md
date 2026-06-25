# The beamline

*The part of ESM CORA models today, as areas you can jump to: the optics and monochromator spine, the ARPES UHV sample, and the electron analyzer, plus the controls. First cut.*

ESM is the NSLS-II Electron Spectro-Microscopy beamline at sector 21-ID. Its PV zones run `XF:21IDA` (front-end optics), `XF:21IDB` (the PGM), `XF:21IDC` (branch optics + exit slits), and `XF:21ID1-ES` / `XF:21IDD-ES` (the ARPES endstation). This cut models the operational core of the ARPES branch; the XPEEM/LEEM branch and the simulated devices are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the beam, the [Sample](sample.md) that orients the specimen in UHV at low temperature, and the [Detector](detector.md) that records the photoelectrons. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the two EPUs, the front-end mirror M1 and the polarization diagnostic, the plane-grating monochromator and M3, and the KB refocusing pair M4A, the M4B mirror, and the resolution-defining exit slits.
- [Sample](sample.md): the ARPES UHV cryostat sample manipulator and the cryostat temperature controller.
- [Detector](detector.md): the hemispherical electron energy analyzer and the beam-current flux monitors.

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, and the bluesky-plan / queue-server orchestration CORA's edge replaces. The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum for the UHV optics and endstation; cryogens for the cryostat); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations). ESM graduates `Manipulator`, reuses the graduated `GratingMonochromator`, and introduces `ElectronAnalyzer` (since graduated by SST).
