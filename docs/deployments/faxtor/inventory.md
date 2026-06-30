# Inventory

*The CORA Asset model for the operational core of FAXTOR modelled today: the planned device tree and what still needs confirming.*

This cut models the shared optics (the wiggler source, the double multilayer monochromator, the filters and slits) and the fast-tomography experiment endstation (the rotary, the sample positioning, the fast shutter, and the scintillator + camera detector). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/faxtor/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. FAXTOR, CORA's first ALBA deployment, **coins no new Family and changes nothing in the catalog**: it is a tomography beamline that reuses the imaging Families the fleet already carries (the 2-BM pilot and the MAX IV TomoWISE design). ALBA publishes no per-beamline device manifest, so no control handles and no vendor Models are bound.

## The Asset tree

Root Asset `FAXTOR` (`tier = Unit`, `facility_code = alba`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `FAXTOR` | `Unit` | (root) | - | bound to the ALBA Site |
| `StorageRing` | `Device` | StorageRing (loose) | - | ALBA 3 GeV ring state, observe-only (MACHINE-1) |
| `Wiggler` | `Device` | InsertionDevice | faxtor-optics | multipole-wiggler source; period / field pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | faxtor-optics | double multilayer monochromator; 8-50 keV mono (MONO-1) |
| `BeamFilter` | `Device` | Filter | faxtor-optics | filtered-white-beam filter set; 30-70 keV (FILT-1) |
| `BeamSlit` | `Device` | Slit | faxtor-optics | beam-defining slits (OPT-2) |
| `FocusingMirror` | `Device` | Mirror | faxtor-optics | focusing / harmonic-rejection mirrors; not published, deferred (OPT-1) |
| `SampleTable` | `Device` | Table | faxtor-experiment | sample-positioning support table; DoF pending (SAMPLE-1) |
| `Rotary` | `Device` | RotaryStage | faxtor-experiment | tomographic rotation, continuous up to 20 Hz; master clock (SAMPLE-1, TRIG-1) |
| `SamplePositioning` | `Device` | LinearStage | faxtor-experiment | sample centring / centre-of-rotation stage (SAMPLE-1) |
| `FastShutter` | `Device` | Shutter | faxtor-experiment | sample-side fast shutter (SAMPLE-1) |
| `Scintillator` | `Device` | Scintillator | faxtor-experiment | X-ray-to-visible screen; material pending (DET-1) |
| `Camera` | `Device` | Camera | faxtor-experiment | fast imaging camera, up to 20 Hz; model not published (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Filter`, `Slit`, `Mirror`, `Table`, `RotaryStage`, `LinearStage`, `Shutter`, `Scintillator`, `Camera`. Loose family reused from siblings: `StorageRing` (machine-state observe-only). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch grouping of the endstation | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Wiggler period, poles, field | `Wiggler` | `unknown-pending-confirmation` | (SRC-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| DMM coating, d-spacing, energy partition | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Filter materials and thicknesses | `BeamFilter` | `unknown-pending-confirmation` | (FILT-1) |
| Mirror presence, coatings, handles | `FocusingMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis map | `BeamSlit` | `unknown-pending-confirmation` | (OPT-2) |
| Endstation stage stack and models | `SampleTable`, `Rotary`, `SamplePositioning`, `FastShutter` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Triggering / synchronization scheme | `Rotary` | `unknown-pending-confirmation` | (TRIG-1) |
| Camera sensor / frame rate / model, scintillator | `Camera`, `Scintillator` | `unknown-pending-confirmation` | (DET-1) |
| Tango / Sardana / IcePAP control handles | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| ALBA PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Vacuum extent and supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
