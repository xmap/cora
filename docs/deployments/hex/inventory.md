# Inventory

*The CORA Asset model for the operational core of HEX modelled today: the planned device tree and what still needs confirming.*

This cut carries the device walk in the two operational enclosures, the `hex-foe` First Optics Enclosure and the `hex-endstation` F-hutch; the B / C / D / E hutches are declared as device-free forward-looking shells (no devices in this cut), and the monochromatic focusing optic and any user-brought in-situ rigs are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/hex/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. HEX coins **no new Family and changes nothing in the catalog**: the imaging and diffraction reuse the existing `Camera` / `Scintillator` / `RotaryStage` / `LinearStage` / `EnergyDispersiveSpectrometer` / `InsertionDevice` / `Monochromator` / `Filter` vocabulary, and the GeRM energy-dispersive detector is the third consumer of the existing `EnergyDispersiveSpectrometer` Family (see [Model](model.md#the-germ-strip-detector-reuses-an-earned-family)). Control handles are filled from the profile collection where present; no vendor Models are bound.

## The Asset tree

Root Asset `HEX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `HEX` | `Unit` | (root) | - | bound to the NSLS-II Site; 27-ID |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only (MACHINE-1) |
| `Wiggler` | `Device` | InsertionDevice | hex-foe | superconducting wiggler (4.3 T, 70 mm period, 1.2 m, cell 27); cryogen-free (SCW-1) |
| `BeamFilters` | `Device` | Filter | hex-foe | FOE low-energy beam-hardening filters (SiC / Cu, per branch) (FILT-1) |
| `Monochromator` | `Device` | Monochromator | hex-foe | bent-Laue first crystal, in / out for monochromatic vs white beam (MONO-1, MONO-2) |
| `BeamEnergy` | `Device` | PseudoAxis | hex-foe | incident-energy axis over the monochromator; 30 to 200 keV monochromatic (MONO-2) |
| `FoeSlit` | `Device` | Slit | hex-foe | front-end defining slits (center branch in use; inboard / outboard for future hutches) (BRANCH-1) |
| `SampleTower` | `Device` | Table | hex-endstation | reconfigurable sample tower, up to 500 kg, removable, configs A to D (STAGE-1) |
| `SampleRotation` | `Device` | RotaryStage | hex-endstation | tomographic rotation (continuous fly and stepped) (STAGE-1) |
| `SampleStage` | `Device` | LinearStage | hex-endstation | sample x / y / z translations (STAGE-1) |
| `ImagingCamera` | `Device` | Camera | hex-endstation | Kinetix sCMOS imaging / tomography cameras (`XF:27ID1-BI{Kinetix-Det:N}`) (DET-3) |
| `ImagingScintillator` | `Device` | Scintillator | hex-endstation | imaging scintillator-lens table ("2 & 4 mm", "20 & 40 mm", "Dual cam") (DET-3) |
| `HighSpeedCamera` | `Device` | Camera | hex-endstation | Phantom Veo high-speed camera for time-resolved radiography (DET-3) |
| `FlatPanelDetector` | `Device` | Camera | hex-endstation | PerkinElmer XRD1621 flat panel, inferred ADXD detector (`XF:27ID1-ES{PE-Det:1}`) (DET-1) |
| `EnergyDispersiveDetector` | `Device` | EnergyDispersiveSpectrometer | hex-endstation | GeRM germanium strip detector for EDXD (`XF:27ID1-ES{GeRM-Det:1}`); third consumer of the Family (DET-2) |
| `DetectorStage` | `Device` | LinearStage | hex-endstation | the detector / optics positioning that switches technique in the one endstation (TECH-1, DET-1) |

Cross-cutting [controls](equipment/controls.md): the motion layer (Phytron and Delta Tau PowerBrick controllers) and the fly-scan triggering are observed but not modelled as device instances in this cut, pending their per-axis functional map; CORA does not invent a controller instance from vendor names alone (`CTRL-1`).

Families reused from the catalog: `InsertionDevice`, `Filter`, `Monochromator`, `PseudoAxis`, `Slit`, `Table`, `RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `EnergyDispersiveSpectrometer`. Loose families reused from siblings: `StorageRing` (supply / machine state). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Six-enclosure topology, only A and F operational | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Satellite-building identity (Bldg. 742 or separate) | `hex-endstation` | `unknown-pending-confirmation` | (SAT-1) |
| Source-to-endstation distance and per-hutch z table | the beam path | `unknown-pending-confirmation` | (LAYOUT-1) |
| Front-end branch optics (provisions vs installed) | `FoeSlit` | `unknown-pending-confirmation` | (BRANCH-1) |
| Control handles (endstation from config; FOE pending) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Wiggler pole count and critical energy | `Wiggler` | `unknown-pending-confirmation` | (SCW-1) |
| Monochromator crystal material, count, d-spacing | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Monochromatic upper energy (150 vs 200 keV) | `BeamEnergy` | `unknown-pending-confirmation` | (MONO-2) |
| FOE filter materials and thicknesses | `BeamFilters` | `unknown-pending-confirmation` | (FILT-1) |
| The monochromatic focusing optic | (deferred) | `unknown-pending-confirmation` | (FOCUS-1) |
| Sample tower configs, capacity, motorized axes | `SampleTower`, `SampleRotation`, `SampleStage` | `unknown-pending-confirmation` | (STAGE-1) |
| Installed in-situ rigs | (deferred) | `unknown-pending-confirmation` | (INSITU-1) |
| PerkinElmer model, pixels, ADXD role | `FlatPanelDetector` | `unknown-pending-confirmation` | (DET-1) |
| GeRM channel count, resolution, gauge volume | `EnergyDispersiveDetector` | `unknown-pending-confirmation` | (DET-2) |
| Kinetix default and scintillator / lens set | `ImagingCamera`, `ImagingScintillator` | `unknown-pending-confirmation` | (DET-3) |
| Vacuum extent and cooling supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
| Operator pool and NYSERDA allocation policy | the governance | `unknown-pending-confirmation` | (GOV-1) |
| Technique set; PDF / 3DXRD not offered | the techniques | `unknown-pending-confirmation` | (TECH-1) |
