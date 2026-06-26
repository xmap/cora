# Inventory

*The CORA Asset model for the operational core of I13-1 modelled today: the planned device tree and what still needs confirming.*

This is a **deliberately partial** first cut: the dodal source (`src/dodal/beamlines/i13_1.py`) exposes only the coherence-branch endstation (the piezo sample stage, the side viewing camera, the Merlin detector), so the shared I13 source and optics are deferred, not invented (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i13-1/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. I13-1, CORA's first coherent lensless-imaging beamline, coins **no new Family and changes nothing in the catalog**: the coherent imaging is an acquisition shape (a Method), not a device class, so the raster stage binds `LinearStage` and the detectors bind `Camera` (see [Model](model.md#what-makes-i13-1-new)). Control handles are filled from dodal; no vendor Models are bound.

## The Asset tree

Root Asset `I13-1` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `I13-1` | `Unit` | (root) | - | bound to the Diamond Site; the I13 coherence branch (BL13J) |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only; shared source / optics deferred (MACHINE-1, SRC-1, OPT-1) |
| `SampleStage` | `Device` | LinearStage | i13-1 | PI piezo sample-scanning stage (the ptychography raster), `BL13J-MO-PI-02` (SAMPLE-1) |
| `SideCamera` | `Device` | Camera | i13-1 | Aravis / GenICam side viewing camera for alignment, `BL13J-OP-FLOAT-03` (DET-1) |
| `Detector` | `Device` | Camera | i13-1 | Merlin (Medipix3) photon-counting coherent-diffraction detector, `BL13J-EA-DET-04` (DET-1) |

Families reused from the catalog: `LinearStage`, `Camera`. Loose families reused from siblings: `StorageRing` (supply). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| I13-1 hutch grouping and the I13-2 / shared-source relation | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The shared I13 undulator source | the source | `unknown-pending-confirmation` | (SRC-1) |
| The shared I13 optics (mono, mirrors, slits) | the optics | `unknown-pending-confirmation` | (OPT-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosure | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Sample-stage axes and the fixed-angle frame | `SampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Merlin detector config and the side-camera role | `Detector`, `SideCamera` | `unknown-pending-confirmation` | (DET-1) |
| Vacuum extent | `resources` | `unknown-pending-confirmation` | (SUP-1) |
