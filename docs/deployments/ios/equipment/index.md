# The beamline

*The part of IOS CORA models today, as areas you can jump to: the optics and monochromator spine, the AP-PES sample manipulator, and the analyzer and yield detectors, plus the controls. First cut.*

IOS is the NSLS-II ambient-pressure soft X-ray spectroscopy beamline on the outboard 23-ID-2 branch, the twin of [CSX](../../csx/index.md). Its PV zones run `XF:23IDA` (front-end optics), `XF:23ID2-OP` (the branch optics, the VLS-PGM and the KB system), `XF:23ID2-ES` (the endstation and the SPECS analyzer), and `XF:23ID2-BI` (the branch beam instrumentation). This cut models the operational core across them; the ambient-pressure reaction cell and the sample-transfer load-lock are deferred (see [Model](../model.md#deliberately-not-here-yet)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, and energy-selects the beam, the [Sample](sample.md) that places the specimen in the analyzer focus, and the [Detector](detector.md) that records the photoelectron and yield signals. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the two canted EPUs, the front-end mirrors, the VLS-PGM, the branch mirror M3B, the deflecting mirror DM1, the Kirkpatrick-Baez focusing pair, and the branch slits.
- [Sample](sample.md): the AP-PES four-axis manipulator, the XAS sample stage, the surface-prep ion gun, and the deferred ambient-pressure reaction cell.
- [Detector](detector.md): the SPECS hemispherical analyzer, the Vortex and Xspress3 fluorescence detectors, the scaler and electron-yield chain, the Au-mesh I0 monitor, and the exit-slit diagnostic camera.

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, and the bluesky-plan orchestration CORA's edge replaces. The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum for the UHV optics and endstation); carried in the descriptor. The ambient-pressure process gas the operando cell would draw on is deferred (`INSITU-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations). IOS adds no new family; every device reuses an existing catalog Family.
