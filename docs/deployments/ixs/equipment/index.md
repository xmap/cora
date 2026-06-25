# The beamline

*The part of IXS CORA models today, as areas you can jump to: the source and monochromator spine, the hard X-ray sample, and the spectrometer, plus the controls. First cut.*

IXS is the NSLS-II momentum-resolved hard X-ray inelastic-scattering beamline at sector 10-ID, and CORA's first hard inelastic-scattering deployment. Its PV zones run `FE:C10A` (front end), `XF:10IDA` (the double-crystal monochromator and first diagnostics), `XF:10IDB` (the high-resolution monochromator and secondary source), `XF:10IDC` (transport optics and table), and `XF:10IDD` (the IXS endstation). This cut models the operational core across them; the simulated devices and the legacy SPEC macros are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the incident beam, the [Sample](sample.md) that places the specimen at a chosen position and angle, and the [Detector](detector.md) that sets the momentum transfer, energy-analyzes the scattered beam, and counts it. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the IVU22 in-vacuum undulator, the front-end slit and the CRL transfocator, the Si(111) double-crystal monochromator with its slit and beam-position monitor, the high-resolution monochromator with its secondary source aperture, the transport optics and table, and the endstation KB mirrors, slit, pinhole, absorber wheel, and optics manipulator. The incident energy is a pseudo-axis over the DCM and the high-resolution mono.
- [Sample](sample.md): the sample positioning table and the sample-environment translations.
- [Detector](detector.md): the six-circle scattering spectrometer arm that sets the momentum transfer Q, the diced crystal energy analyzer that selects a fixed final energy, its slit and per-crystal thermal stabilization, and the counting detectors (the quad electrometers and the incident-flux scaler).

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, and the bluesky-plan / queue-server orchestration CORA's edge replaces. The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum for the optics and the spectrometer beam path, and the thermal stabilization the diced crystal analyzer draws on); carried in the descriptor.

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the one loose family held at n=1.
