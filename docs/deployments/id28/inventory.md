# Inventory

*The CORA Asset model for the operational core of ID28 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared optics (the high-resolution backscattering monochromator, the focusing mirrors, the beam-defining slits) and the eh1 IXS spectrometer endstation (the sample stage, its temperature environments, and the multi-analyzer spectrometer arm). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id28/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. ID28, CORA's second ESRF beamline, **coins no new Family**: the multi-analyzer spectrometer arm binds the catalog `SpectrometerArm` (a further consumer after SIX + ID32 that reinforced the now-landed graduation), and everything else reuses an existing catalog or loose Family (see [Model](model.md#a-further-spectrometerarm-consumer-held)). Control handles are filled from the BLISS Beacon config (BLISS / Tango / IcePAP addresses); no vendor Models are bound.

## The Asset tree

Root Asset `ID28` (`tier = Unit`, `facility_code = esrf`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `ID28` | `Unit` | (root) | - | bound to the ESRF Site |
| `StorageRing` | `Device` | StorageRing (loose) | - | ESRF-EBS ring state via BLISS MachInfo, observe-only (MACHINE-1) |
| `FrontEndShutter` | `Device` | Shutter | id28-optics | the front-end shutter (BLISS `fe`, TangoShutter) (PSS-1) |
| `Undulator` | `Device` | InsertionDevice | id28-optics | two in-vacuum undulators IVU22a / IVU13-3c (BLISS `u22gap` / `u133gap`) (SRC-1) |
| `Monochromator` | `Device` | Monochromator | id28-optics | high-resolution backscattering mono (BLISS PI_E518, pimth / pimchi) (MONO-1) |
| `BeamEnergy` | `Device` | PseudoAxis | id28-optics | incident-energy axis via the ASL F700 crystal-temperature controller (monot / deltae), not an angular mono; the meV scan is the IXS measurement (MONO-1) |
| `HorizontalFocusingMirror` | `Device` | Mirror | id28-optics | HFM two-bender mirror (BLISS hfm_ctrl) (OPT-1) |
| `VerticalFocusingMirror` | `Device` | Mirror | id28-optics | VFM two-bender mirror (BLISS vfm_ctrl) (OPT-1) |
| `BeamPositionMonitor` | `Device` | BeamPositionMonitor | id28-optics | the oh2 Elettra BPM; graduated catalog Family presenting `Sensor`, position-measuring (DIAG-1) |
| `PrimarySlit` | `Device` | Slit | id28-optics | the primary beam-defining slits (BLISS slits_ph / slits_pv) (OPT-2) |
| `MonoSlit` | `Device` | Slit | id28-optics | the main-mono slit (BLISS slits_mx) (OPT-2) |
| `SampleStage` | `Device` | LinearStage | id28-eh1 | the IXS scattering-geometry sample stage (sax / say / saz, th / sphi / chi, eh1_ss iceid285, SmarAct) (SAMPLE-1) |
| `SampleSlit` | `Device` | Slit | id28-eh1 | the sample-defining slits (BLISS slits_sh / slits_sv) (OPT-2) |
| `SampleTemperatureController` | `Device` | TemperatureController | id28-eh1 | the 10 K displex LakeShore 340 (Oxford 700 + nanodac gas blower as alternatives) (TEMP-1) |
| `SpectrometerArm` | `Device` | SpectrometerArm | id28-eh1 | the IXS multi-analyzer spectrometer (BLISS tth_multilayer two-theta arm + a1..a9 inclined analyzer crystals); further consumer, graduated Family (RIXS-1, IXS-1) |
| `Detector` | `Device` | Camera | id28-eh1 | the Basler / PCO detectors plus the per-analyzer deta1..deta9 counters (DET-1) |

Families reused from the catalog: `Shutter`, `InsertionDevice`, `Monochromator`, `PseudoAxis`, `Mirror`, `Slit`, `LinearStage`, `TemperatureController`, `Camera`, `SpectrometerArm` (graduated across SIX + ID32 RIXS/XES + ID28; ID28 is a further consumer that reinforced it, RIXS-1), `BeamPositionMonitor` (graduated catalog Family presenting `Sensor`, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux, DIAG-1). Loose families reused from siblings: `StorageRing` (supply). No new family is coined; ID28's SpectrometerArm sighting reinforced the graduation that has since landed.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch grouping of the optics + endstation | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Undulator period and segments | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (BLISS / Tango / IcePAP) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| ESRF PSS permit signals behind the shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Backscattering crystal, meV resolution, energy rule | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and bender mechanics | the focusing mirrors | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis map | `PrimarySlit`, `MonoSlit`, `SampleSlit` | `unknown-pending-confirmation` | (OPT-2) |
| BPM position-vs-flux | `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| SpectrometerArm geometry (Family graduated) | `SpectrometerArm` | `unknown-pending-confirmation` | (RIXS-1) |
| Analyzer-crystal array count and child-Asset identity | `SpectrometerArm` | `unknown-pending-confirmation` | (IXS-1) |
| Sample-stage axes | `SampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Sample-temperature environments | `SampleTemperatureController` | `unknown-pending-confirmation` | (TEMP-1) |
| Per-analyzer detectors and imaging cameras | `Detector` | `unknown-pending-confirmation` | (DET-1) |
| Vacuum extent and cryogen supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
