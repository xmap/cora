# Inventory

*The CORA Asset model for the operational core of 12-ID-E modelled today: the planned device tree and what still needs confirming.*

This cut models the shared 12-ID optics and the 12-ID-E USAXS / SAXS / WAXS endstation; the simulated devices, the legacy SPEC heritage, and the optional in-situ load frame are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/12-id-e/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. 12-ID-E, CORA's first Bonse-Hart USAXS beamline, coins **no new Family and changes nothing in the catalog**: the Bonse-Hart crystal stages reuse `RotaryStage`, the autoranging photodiode and flux monitors reuse `FluxMonitor`, the temperature stages reuse the graduated `TemperatureController`, the area detectors reuse `Camera` (see [Model](model.md#what-makes-12-id-e-new)). Control handles are filled from the instrument config; no vendor Models are bound.

## The Asset tree

Root Asset `12-ID-E` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `12-ID-E` | `Unit` | (root) | - | bound to the APS Site; Sector 12 |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring current, observe-only (MACHINE-1) |
| `Monochromator` | `Device` | Monochromator | 12-ID-optics | the shared 12-ID double-crystal mono (MONO-1) |
| `Attenuator` | `Device` | Filter | 12-ID-optics | Al/Ti attenuator filter bank, `12idPyFilter:` (ATTN-1) |
| `GuardSlit` | `Device` | Slit | 12-ID-optics | guard slit (OPT-2) |
| `UsaxsSlit` | `Device` | Slit | 12-ID-optics | USAXS-defining slit (OPT-2) |
| `CollimatorStage` | `Device` | RotaryStage | 12-ID-E | Bonse-Hart collimator crystal stage, rocking rotation (BONSE-1) |
| `AnalyzerStage` | `Device` | RotaryStage | 12-ID-E | Bonse-Hart analyzer crystal stage, rocking rotation (BONSE-1) |
| `SampleStage` | `Device` | LinearStage | 12-ID-E | sample positioning stage (SAMPLE-1) |
| `SampleRotator` | `Device` | RotaryStage | 12-ID-E | PI C-867 sample rotator, `usxPI:c867:c0:m1` (SAMPLE-1) |
| `LinkamStage` | `Device` | TemperatureController | 12-ID-E | Linkam T96 temperature stage, `usxLINKAM:tc1:` (TEMP-1) |
| `Ptc10Controller` | `Device` | TemperatureController | 12-ID-E | PTC10 multi-channel temperature controller, `usxTEMP:tc1:` (TEMP-1) |
| `PhotodiodeDetector` | `Device` | FluxMonitor | 12-ID-E | UPD autoranging photodiode, the primary USAXS detector (DET-1) |
| `FluxMonitors` | `Device` | FluxMonitor | 12-ID-E | I0 / I00 / I000 / TRD incident and transmitted monitors (DET-1) |
| `Scaler` | `Device` | FluxMonitor | 12-ID-E | counting scaler, `usxLAX:vsc:c0` (DET-1) |
| `DetectorStage` | `Device` | LinearStage | 12-ID-E | USAXS / SAXS detector translation stages (OPT-2) |
| `SaxsDetector` | `Device` | Camera | 12-ID-E | pinhole SAXS Pilatus area detector (DET-1) |
| `WaxsDetector` | `Device` | Camera | 12-ID-E | WAXS Pilatus area detector on its translation (DET-1) |

Families reused from the catalog: `Monochromator`, `Filter`, `Slit`, `RotaryStage`, `LinearStage`, `TemperatureController`, `FluxMonitor`, `Camera`. Loose families reused from siblings: `StorageRing`. No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Optics-vs-experiment hutch grouping | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Undulator period and type | the source | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Mono cut, energy range, real PVs | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Attenuator foil set and catalog home | `Attenuator` | `unknown-pending-confirmation` | (ATTN-1) |
| Slit and stage blade-axis maps | the slits and stages | `unknown-pending-confirmation` | (OPT-2) |
| Bonse-Hart crystal cut and rocking-axis map | `CollimatorStage`, `AnalyzerStage` | `unknown-pending-confirmation` | (BONSE-1) |
| Sample stage axes and rotator role | `SampleStage`, `SampleRotator` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Linkam range and PTC10 channels | `LinkamStage`, `Ptc10Controller` | `unknown-pending-confirmation` | (TEMP-1) |
| In-situ load-frame modelling | (deferred device) | `unknown-pending-confirmation` | (LOADFRAME-1) |
| Photodiode gain decades, flux-monitor and detector map | `PhotodiodeDetector`, `FluxMonitors`, `SaxsDetector`, `WaxsDetector` | `unknown-pending-confirmation` | (DET-1) |
| Vacuum extent | `resources` | `unknown-pending-confirmation` | (SUP-1) |
| USAXS Capability / Method | the technique | `unknown-pending-confirmation` | (USAXS-1) |
