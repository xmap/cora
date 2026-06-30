# Inventory

*The CORA Asset model for the operational core of 8.3.2 modelled today: the planned device tree and what still needs confirming.*

This cut models the source (the storage-ring state and the Superbend), the conditioning optics (the monochromator, the slits, and the attenuating filter), the tomographic sample stack (the rotary and the sample-centring stages), and the indirect detector (the scintillator, the camera objective, the camera, and the motorized detector stack). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/8-3-2/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. 8.3.2, CORA's first ALS deployment, **coins no new Family and changes nothing in the catalog**: it is a tomography beamline that reuses the imaging Families the fleet already carries (the 2-BM pilot, the NSLS-II FXI design, and the ALBA FAXTOR design). The device **structure** is read from the DXchange / DXfile HDF5 data record; the **live BCS control handles are not public** (BCS is LabVIEW, not EPICS), so no control handles and no vendor Models are bound.

## The Asset tree

Root Asset `8.3.2` (`tier = Unit`, `facility_code = als`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `8.3.2` | `Unit` | (root) | - | bound to the ALS Site |
| `StorageRing` | `Device` | StorageRing (loose) | 8-3-2-hutch | ALS ring state, observe-only (MACHINE-1) |
| `Superbend` | `Device` | InsertionDevice | 8-3-2-hutch | superconducting bending-magnet source, 6-43 keV; recorded as a Supply (SRC-1) |
| `Monochromator` | `Device` | Monochromator | 8-3-2-hutch | energy-setting optic; `energy` master axis, Z2 / turret1 / turret2 / TC2 / TC3 in the data record (MONO-1) |
| `BeamSlit` | `Device` | Slit | 8-3-2-hutch | horizontal (A_Door / A_Wall / center / size) + vertical (Lead_Flag) slits (OPT-2) |
| `BeamFilter` | `Device` | Filter | 8-3-2-hutch | attenuating filter; `filter_y` position axis (FILT-1) |
| `SampleRotary` | `Device` | RotaryStage | 8-3-2-hutch | tomographic rotation, fly-scan trigger master; axis identity pending (SAMPLE-1, ROT-1, TRIG-1) |
| `SamplePositioning` | `Device` | LinearStage | 8-3-2-hutch | sample centring; `sample_x` / `sample_y` (SAMPLE-1) |
| `Scintillator` | `Device` | Scintillator | 8-3-2-hutch | X-ray-to-visible screen; `scintillator_type` in the data record (DET-1) |
| `CameraObjective` | `Device` | Objective | 8-3-2-hutch | microscope objective; `camera_objective` magnification in the data record (DET-1) |
| `Camera` | `Device` | Camera | 8-3-2-hutch | imaging camera; model / pixel_size / binning / exposure are per-dataset values (DET-1) |
| `DetectorStack` | `Device` | LinearStage | 8-3-2-hutch | detector motion; `camera_distance` (propagation), `camera_elevation`, `tilt_motor` (DET-2) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Slit`, `Filter`, `RotaryStage`, `LinearStage`, `Scintillator`, `Objective`, `Camera`. Loose family reused from siblings: `StorageRing` (machine-state observe-only). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch grouping (single vs optics + experiment) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Superbend field and critical energy | `Superbend` | `unknown-pending-confirmation` | (SRC-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Monochromator mechanism, d-spacing, energy wiring | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Slit blade-axis map | `BeamSlit` | `unknown-pending-confirmation` | (OPT-2) |
| Filter materials and thicknesses | `BeamFilter` | `unknown-pending-confirmation` | (FILT-1) |
| Sample-stage stack and models | `SampleRotary`, `SamplePositioning` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Which axis is the tomographic rotation | `SampleRotary` | `unknown-pending-confirmation` | (ROT-1) |
| Triggering / synchronization scheme | `SampleRotary` | `unknown-pending-confirmation` | (TRIG-1) |
| Camera sensor / frame rate / model, scintillator, objective set | `Camera`, `Scintillator`, `CameraObjective` | `unknown-pending-confirmation` | (DET-1) |
| Detector-stack axis models and propagation wiring | `DetectorStack` | `unknown-pending-confirmation` | (DET-2) |
| BCS / LabVIEW control handles | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| ALS PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Vacuum extent and supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
| ALS-U upgrade fate of 8.3.2 | the beamline | `unknown-pending-confirmation` | (ALSU-1) |
