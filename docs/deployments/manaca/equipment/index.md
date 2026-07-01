# The beamline

*The part of MANACA CORA models today, as areas you can jump to: the optics, the MX experiment endstation, and the detector, plus the controls. First cut.*

MANACA is Sirius's macromolecular-crystallography beamline, the first MX beamline CORA models at Sirius (after the [MOGNO](../../mogno/index.md) tomography scaffold). An undulator feeds a monochromator (5-20 keV) into a single MX experiment endstation: a goniometer holds a crystal (mounted from an automated 48-pin sample changer) and rotates it while the area detector reads frames. This cut models the operational core across the optics, the sample stage, and the detector. The model is reverse-engineered from Sirius's public facility pages; LNLS publishes no per-beamline PV manifest, so the EPICS / MXCuBE handles are not bound, carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and energy-selects the incident beam, the [Sample](sample.md) that holds and orients the crystal at the experiment endstation, and the [Detector](detector.md) that records the diffraction. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, grouping pending (`ENC-1`): a `manaca-optics` hutch and the `manaca-experiment` endstation hutch.

## Stations

- [Source](../beamline.md): the Sirius storage-ring state (a loose `StorageRing`, observe-only, `MACHINE-1`); the front-end shutter bound to `Shutter` (`PSS-1`); the monochromator bound to `Monochromator` (`MONO-1`); the master energy `PseudoAxis` (`ENERGY-1`); and the attenuators bound to `Filter` (`FILT-1`). This page is generated from the descriptor.
- [Sample](sample.md): the goniometer bound to the graduated `Goniometer` (`GONIO-1`), the cryostream bound to `TemperatureController` (`TEMP-1`), the on-axis backlight bound to the catalog `Backlight` (`DET-1`), and the beamstop bound to `BeamStop` (`SAMPLE-1`).
- [Detector](detector.md): the area detector bound to `Camera` (`DET-1`), its translation stage bound to `LinearStage`, the on-axis viewing camera bound to `Camera`, and the flux monitor bound to `FluxMonitor` (`DIAG-1`).

## Shared

- [Controls](controls.md): the Sirius EPICS device floor + MXCuBE3, and the MX orchestration CORA's edge conducts over or drives through (Bluesky / sophys is a named facility direction, `ORCH-1`). No public per-beamline PV manifest exists, so the handles are not bound, carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum, and the cryostream liquid nitrogen); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
