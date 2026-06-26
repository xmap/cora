# Inventory

*The CORA Asset model for the operational core of 13-ID-D modelled today: the planned device tree and what still needs confirming.*

This cut models the shared 13-ID-A optics, the 13-ID-D high-pressure endstation, and the diamond anvil cell. The 13-BM stations and the large-volume press are out of this station's scope (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/13-id-d/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. 13-ID-D, CORA's first extreme-conditions deployment, coins **one new loose Family**, `PressureCell`, for the diamond anvil cell (no fleet analog for a high-pressure sample environment); everything else reuses the catalog (see [Model](model.md#new-loose-family-the-pressurecell)). The control handles are reconstructed from the GSECARS EPICS support tree at medium confidence; no vendor Models are bound.

## The Asset tree

Root Asset `13-ID-D` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `13-ID-D` | `Unit` | (root) | - | bound to the APS Site; sector 13 (GSECARS) |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only (MACHINE-1) |
| `Monochromator` | `Device` | Monochromator | 13-ID-optics | shared 13-ID-A Si double-crystal mono, `13IDA:` (MONO-1) |
| `BeamEnergy` | `Device` | PseudoAxis | 13-ID-optics | derived beamline-energy axis, `13IDE:En` (MONO-1) |
| `FocusingMirror` | `Device` | Mirror | 13-ID-optics | K-B + carbon mirrors; curvature a PseudoAxis (OPT-1) |
| `BeamSlit` | `Device` | Slit | 13-ID-optics | beam-defining + DAC table-top slits (DACV / DACH) (OPT-2) |
| `CleanupPinhole` | `Device` | Aperture | 13-ID-optics | clean-up pinhole before the cell (APERTURE-1) |
| `Attenuator` | `Device` | Filter | 13-ID-optics | attenuator / filter set, `13IDD:filter:` (ATTN-1) |
| `PressureCell` | `Device` | PressureCell (loose) | 13-ID-D | the diamond anvil cell: membrane pressure (PACE5000 `13IDD_PACE5000:PC1:`, Regulator), double-sided laser heating (HEAT-1), in-situ P/T metrology; NEW loose Family, n=1 (HP-1, PRESSURE-1) |
| `SampleStage` | `Device` | Goniometer | 13-ID-D | DAC positioning stage / micro-diffractometer (Galil + XPS-16) (SAMPLE-1) |
| `SampleTable` | `Device` | Table | 13-ID-D | the DAC lift table supporting the cell (SAMPLE-1) |
| `MetrologySpectrometer` | `Device` | Camera | 13-ID-D | LightField spectrometer for the cell's P/T metrology, `13IDDLF1:` (HP-1) |
| `AreaDetector` | `Device` | Camera | 13-ID-D | Eiger2 X 9M (`13EIG2_9M:`); Pilatus 1M CdTe / Si alternatives (DET-1) |
| `DetectorStage` | `Device` | LinearStage | 13-ID-D | detector table + 2theta arm; the swing PseudoAxis binding deferred (DET-1) |
| `FluxMonitor` | `Device` | FluxMonitor | 13-ID-D | ion chambers (`13IDD:scaler1`) + DAC photodiode (DET-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | 13-ID-D | XGLab Dante MCA, `13IDD_Dante1:` (DET-1) |
| `SampleIllumination` | `Device` | Backlight (loose) | 13-ID-D | fibre sample illumination for the viewing microscope (DET-1) |

Families reused from the catalog: `Monochromator`, `PseudoAxis`, `Mirror`, `Slit`, `Aperture`, `Filter`, `Goniometer`, `Table`, `Camera`, `LinearStage`, `FluxMonitor`, `EnergyDispersiveSpectrometer`. Loose families reused from siblings: `StorageRing` (supply), `Backlight` (held under review). Coined loose at n=1 (new to the catalog, graduates nothing): `PressureCell`.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Optics-vs-endstation hutch grouping + laser enclosure | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Undulator detail | the source | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs, EPICS-native reconstruction) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS + laser-safety permit signals | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Mono cut, energy range, partition rule | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and curvature axes | `FocusingMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis maps | `BeamSlit` | `unknown-pending-confirmation` | (OPT-2) |
| Clean-up pinhole carriers | `CleanupPinhole` | `unknown-pending-confirmation` | (APERTURE-1) |
| Attenuator foil set and catalog home | `Attenuator` | `unknown-pending-confirmation` | (ATTN-1) |
| DAC configuration, heating geometry, metrology | `PressureCell` | `unknown-pending-confirmation` | (HP-1) |
| Heating loop: open-loop power vs temperature setpoint | `PressureCell` | `unknown-pending-confirmation` | (HEAT-1) |
| Laser-safety PLC + excitation-laser host | `PressureCell` | `unknown-pending-confirmation` | (LASER-1) |
| DAC stage axes and controller | `SampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Detector assignment, 2theta arm, channel map | `AreaDetector`, `DetectorStage`, `FluxMonitor`, `FluorescenceDetector` | `unknown-pending-confirmation` | (DET-1) |
| Vacuum extent and high-pressure gas supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
