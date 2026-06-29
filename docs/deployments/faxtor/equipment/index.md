# The beamline

*The part of FAXTOR CORA models today, as areas you can jump to: the shared wiggler source and conditioning optics, the fast-tomography experiment endstation, and the imaging detector, plus the controls. First cut.*

FAXTOR is ALBA's BL31 fast X-ray micro-CT and radiography beamline, CORA's first ALBA deployment. A multipole wiggler feeds a double multilayer monochromator (mono imaging) or a filter set (filtered white beam) into a single experiment endstation for fast continuous-rotation tomography. This cut models the operational core across the source, the sample stage, and the detector. The model is reverse-engineered from ALBA's public facility pages; ALBA publishes no per-beamline device manifest, so the Tango / Sardana / IcePAP handles are not bound, carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, filters, and energy-selects the incident beam, the [Sample](sample.md) that rotates and positions the specimen at the experiment endstation, and the [Detector](detector.md) that converts and records the transmitted beam. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

Two enclosures carry the beamline, grouping pending (`ENC-1`): a shared `faxtor-optics` hutch and the `faxtor-experiment` endstation hutch.

## Stations

- [Source](../beamline.md): the ALBA storage-ring state (a loose `StorageRing`, observe-only, `MACHINE-1`); the multipole wiggler bound to `InsertionDevice` (`SRC-1`); the double multilayer monochromator bound to `Monochromator` (`MONO-1`); the filtered-white-beam filters bound to `Filter` (`FILT-1`); the beam slits (`OPT-2`); and the focusing mirrors (`OPT-1`). This page is generated from the descriptor.
- [Sample](sample.md): the experiment-endstation sample table bound to `Table`, the tomographic rotary stage bound to `RotaryStage`, the sample positioning bound to `LinearStage`, and the fast shutter bound to `Shutter` (`SAMPLE-1`, `TRIG-1`).
- [Detector](detector.md): the scintillator bound to `Scintillator` and the fast imaging camera bound to `Camera`; the camera model is not published, carried pending (`DET-1`).

## Shared

- [Controls](controls.md): the ALBA Tango / Sardana / Taurus control stack, the fleet's second after MAX IV, and the Sardana-macro orchestration CORA's edge conducts over. No public per-beamline device manifest exists, so the handles are not bound, carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, and vacuum); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
