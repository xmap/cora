# Inventory

*The CORA Asset model for the operational core of MOGNO modelled today: the planned device tree and what still needs confirming.*

This cut models the shared source and optics, the nanotomography station, the microtomography station, and the detector chain. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Nanotomography](equipment/nanotomography.md), [Microtomography](equipment/microtomography.md), and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/mogno/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. MOGNO **coins no new Family and changes nothing in the catalog**: it reuses the tomography families the APS 2-BM pilot and NSLS-II FXI established. Unlike the NSLS-II and Diamond scaffolds, MOGNO has no public controls config, so no control handles are filled and no vendor Models are bound: every handle and model is an open question.

## The Asset tree

Root Asset `MOGNO` (`tier = Unit`, `facility_code = sirius`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `MOGNO` | `Unit` | (root) | - | bound to the Sirius Site |
| `StorageRing` | `Device` | StorageRing (loose) | - | Sirius 3 GeV ring state, observe-only (MACHINE-1) |
| `Source` | `Device` | InsertionDevice | mogno-nano | 3.2 T dipole / superbend, quasi-monochromatic cone beam; type and parameters pending (SRC-1) |
| `FocusingMirror` | `Device` | Mirror | mogno-nano | elliptical / KB-style focusing mirrors to the ~100-120 nm nanofocus; count, coatings, handles pending (OPT-1) |
| `BeamSlit` | `Device` | Slit | mogno-nano | beam-defining slits; blade-axis map and handles pending (OPT-2) |
| `SampleRotary` | `Device` | RotaryStage | mogno-nano | nanotomography rotation axis, the master clock; model, encoder, handle pending (STAGE-1) |
| `SampleTripod` | `Device` | LinearStage | mogno-nano | fine three-axis sample positioner (piezo tripod); axis set a per-Asset setting (STAGE-2) |
| `MicroSampleRotary` | `Device` | RotaryStage | mogno-micro | microtomography rotation axis, the master clock; model and handle pending (STAGE-3) |
| `MicroSampleStage` | `Device` | LinearStage | mogno-micro | microtomography sample positioner; axes, model, handles pending (STAGE-3) |
| `Camera` | `Device` | Camera | mogno-micro | high-Z photon-counting (Pimega) + indirect sCMOS roster; per-station pairing and config pending (CAM-1) |
| `Scintillator` | `Device` | Scintillator | mogno-micro | scintillator for the indirect chain (e.g. LuAG:Ce) + Optique Peter microscope; material pending (CAM-2) |
| `Magnification` | `Device` | PseudoAxis | mogno-micro | cone-beam geometric magnification (sample-along-cone zoom); rule pending (MAG-1) |
| `TATU` | `Device` | TimingController | - | FPGA trigger/timer on CompactRIO; hardware-syncs projection acquisition; handles pending (CTRL-1) |
| `SampleMotionController` | `Device` | MotionController | - | drives the sample-side stages; box model and PV namespace pending (CTRL-1) |

Families reused from the catalog: `InsertionDevice`, `Mirror`, `Slit`, `RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `PseudoAxis`, `TimingController`, `MotionController`. Loose families reused from siblings: `StorageRing` (supply, observe-only). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Source type and parameters | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| Working energy set (21.5/39/67.7 vs 22/39/67.5 keV) | `Source` | `unknown-pending-confirmation` | (SRC-2) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Focusing-mirror count, coatings, handles | `FocusingMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis map and handles | `BeamSlit` | `unknown-pending-confirmation` | (OPT-2) |
| Nano rotation stage model, encoder, handle | `SampleRotary` | `unknown-pending-confirmation` | (STAGE-1) |
| Nano sample-tripod axes and model | `SampleTripod` | `unknown-pending-confirmation` | (STAGE-2) |
| Micro-station stage models and handles | `MicroSampleRotary`, `MicroSampleStage` | `unknown-pending-confirmation` | (STAGE-3) |
| Detector roster and per-station pairing | `Camera` | `unknown-pending-confirmation` | (CAM-1) |
| Scintillator material and microscope objectives | `Scintillator` | `unknown-pending-confirmation` | (CAM-2) |
| Cone-beam magnification rule | `Magnification` | `unknown-pending-confirmation` | (MAG-1) |
| Acquisition file format (HDF5 / NeXus / DXchange) | the data file | `unknown-pending-confirmation` | (DATA-1) |
| Control handles (EPICS PVs, TATU, controller boxes) | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| Orchestration: custom mgn-* or migrated to Bluesky | the control seam | `unknown-pending-confirmation` | (ORCH-1) |
| Reconstruction HPC cluster, scheduler, storage path | the compute leg | `unknown-pending-confirmation` | (COMPUTE-1) |
| Sirius PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
