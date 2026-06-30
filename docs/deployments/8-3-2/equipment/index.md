# The beamline

*The part of 8.3.2 CORA models today, as areas you can jump to: the Superbend source and conditioning optics, the tomographic sample stack, and the imaging detector, plus the controls. First cut.*

8.3.2 is the ALS hard X-ray micro-tomography beamline, CORA's first ALS deployment. A Superbend source feeds an energy-setting monochromator (6,000-43,000 eV) and conditioning optics into a tomographic sample stack and an indirect scintillator + camera detector for micro-CT at ~1 micron resolution. This cut models the operational core across the source, the sample stage, and the detector. The model is reverse-engineered from ALS's public facility pages and the public `als-computing` GitHub org; the device structure is read from the DXchange / DXfile HDF5 data record, but ALS runs BCS (LabVIEW, not EPICS) and publishes no per-beamline channel manifest, so the control handles are not bound, carried `confirm` (see [Model](../model.md)).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers and energy-selects the incident beam, the [Sample](sample.md) that rotates and positions the specimen, and the [Detector](detector.md) that converts and records the transmitted beam. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

One enclosure carries the beamline, grouping pending (`ENC-1`): a single `8-3-2-hutch`.

## Stations

- [Source](../beamline.md): the ALS storage-ring state (a loose `StorageRing`, observe-only, `MACHINE-1`); the Superbend bound to `InsertionDevice` and recorded as a Supply (`SRC-1`); the energy-setting monochromator bound to `Monochromator` (`MONO-1`); the horizontal / vertical slits bound to `Slit` (`OPT-2`); and the attenuating filter bound to `Filter` (`FILT-1`). This page is generated from the descriptor.
- [Sample](sample.md): the tomographic rotary stage bound to `RotaryStage` and the sample-centring stage bound to `LinearStage` (`SAMPLE-1`, `ROT-1`, `TRIG-1`).
- [Detector](detector.md): the scintillator bound to `Scintillator`, the camera objective bound to `Objective`, the camera bound to `Camera`, and the motorized detector stack bound to `LinearStage`; detector specs are per-dataset values, the model carried pending (`DET-1`, `DET-2`).

## Shared

- [Controls](controls.md): the ALS BCS / LabVIEW control stack, the fleet's first BCS plane, the emerging Bluesky-over-BCS acquisition layer, and the `splash_flows` data-movement / reconstruction seam CORA observes and subsumes. No public per-beamline channel manifest exists, so the handles are not bound, carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, vacuum, and power); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations).
