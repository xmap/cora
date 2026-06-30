# Inventory

*The CORA Asset model for the operational core of i10 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared soft X-ray optics spine (the PGM and the twin APPLE-II undulators) and both endstations: the RASOR resonant-scattering endstation and the i10-1 magnet endstation. The simulated devices and the upstream diagnostic screens are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i10/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. i10, the second APPLE-II source in the fleet (after i06), coins **no new Family and changes nothing in the catalog**: the APPLE-II undulators reuse `InsertionDevice` and the polarization is a `PseudoAxis`, exactly as i06. Two loose families reach their second sighting and are held under review, not graduated: the RASOR polarization-analysis arm binds the loose `PolarizationAnalyzer` (POL-2) and the i10-1 magnets bind the loose `Magnet` (MAG-1). See [Model](model.md#loose-families-at-a-second-sighting). Control handles are filled from dodal; no vendor Models are bound.

## The Asset tree

Root Asset `I10` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `I10` | `Unit` | (root) | - | bound to the Diamond Site; Sector 10 |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only (MACHINE-1) |
| `UndulatorDownstream` | `Device` | InsertionDevice | i10-optics | downstream (IDD) APPLE-II, `SR10I-MO-SERVC-01` (SRC-1) |
| `UndulatorUpstream` | `Device` | InsertionDevice | i10-optics | upstream (IDU) APPLE-II, `SR10I-MO-SERVC-21` (SRC-1) |
| `Monochromator` | `Device` | GratingMonochromator | i10-optics | soft X-ray plane-grating mono, `BL10I-OP-PGM-01` (MONO-1) |
| `CollimatingMirror` | `Device` | Mirror | i10-optics | first collimating mirror, `BL10I-OP-COL-01` |
| `SwitchingMirror` | `Device` | Mirror | i10-optics | branch-switching mirror (RASOR / i10-1), `BL10I-OP-SWTCH-01` |
| `OpticsSlit` | `Device` | Slit | i10-optics | shared optics-spine slits, `BL10I-AL-SLITS-` (ENC-1) |
| `BeamEnergy` | `Device` | PseudoAxis | i10-optics | incident-energy axis over the PGM and the APPLE-II gap (MONO-1, ENERGY-1) |
| `Polarization` | `Device` | PseudoAxis | i10-optics | the polarization axis over the APPLE-II phase rows (POL-1) |
| `Diffractometer` | `Device` | Goniometer | i10-rasor | RASOR sample circles + two-theta arm, `ME01D-MO-DIFF-01` (DIFF-1) |
| `ReciprocalSpace` | `Device` | PseudoAxis | i10-rasor | reciprocal-space axis over the RASOR circles (DIFF-2) |
| `AnalyzerArm` | `Device` | PolarizationAnalyzer (loose) | i10-rasor | the POLAN polarization-analysis arm, `ME01D-MO-POLAN-01`; second sighting, held (POL-2) |
| `DetectorSlit` | `Device` | Slit | i10-rasor | detector slits before the RASOR point detector, `ME01D-MO-APTR-0` |
| `Pinhole` | `Device` | Aperture | i10-rasor | endstation beam-defining pinhole, `ME01D-EA-PINH-01` (STAGE-1) |
| `SampleStage` | `Device` | LinearStage | i10-rasor | cryostat sample-positioning stage (x / y / z), `ME01D-MO-CRYO-01` (STAGE-1) |
| `SampleTemperatureController` | `Device` | TemperatureController | i10-rasor | Lakeshore 340 cryostat temperature, `ME01D-EA-TCTRL-01` (TEMP-1) |
| `FocusingMirror` | `Device` | Mirror | i10-rasor | RASOR-branch focusing mirror, `BL10I-OP-FOCS-01` |
| `Detector` | `Device` | FluxMonitor | i10-rasor | RASOR point detection: scattered-beam point detector + I0 / fluorescence / drain-current channels, `ME01D-EA-SCLR-01` (DET-1) |
| `Electromagnet` | `Device` | Magnet (loose) | i10-1 | i10-1 electromagnet (set-and-read field), `BL10J-EA-MAGC-01`; second sighting, held (MAG-1) |
| `HighFieldMagnet` | `Device` | Magnet (loose) | i10-1 | superconducting field-sweep magnet, `BL10J-EA-SMC-01`; same Family, sweep is an affordance (MAG-1) |
| `HighFieldMagnetStage` | `Device` | LinearStage | i10-1 | high-field-magnet sample stage, `BL10J-EA-MAG-01` |
| `ElectromagnetStage` | `Device` | LinearStage | i10-1 | electromagnet cryostat sample stage, `BL10J-MO-CRYO-01` (MAG-1) |
| `MagnetTemperatureController` | `Device` | TemperatureController | i10-1 | Lakeshore 336 sample temperature, `BL10J-EA-TCTRL-41` (TEMP-1) |
| `MagnetSlit` | `Device` | Slit | i10-1 | i10-1 branch slits, `BL10J-AL-SLITS-` |
| `MagnetFocusingMirror` | `Device` | Mirror | i10-1 | i10-1-branch focusing mirror, `BL10J-OP-FOCA-01` |
| `MagnetDetector` | `Device` | FluxMonitor | i10-1 | i10-1 point detection: TEY / FY / diode / monitor channels, `BL10J-EA-SCLR-01..02` (DET-1) |

Families reused from the catalog: `InsertionDevice`, `GratingMonochromator`, `Mirror`, `Slit`, `PseudoAxis`, `Goniometer`, `Aperture`, `LinearStage`, `TemperatureController`, `FluxMonitor`. Loose families reused from siblings: `StorageRing` (supply), `PolarizationAnalyzer` (4-ID; second sighting, held POL-2), `Magnet` (4-ID; second sighting, held MAG-1). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch grouping of the three PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| APPLE-II periods, gap range, coordination | `UndulatorDownstream`, `UndulatorUpstream` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| PGM gratings, cff, energy range | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| One-vs-two incident-energy axes | `BeamEnergy` | `unknown-pending-confirmation` | (ENERGY-1) |
| Polarization domain and conversion rule | `Polarization` | `unknown-pending-confirmation` | (POL-1) |
| Diffractometer circle roles and Assembly | `Diffractometer` | `unknown-pending-confirmation` | (DIFF-1) |
| Reciprocal-space inverse-kinematics rule | `ReciprocalSpace` | `unknown-pending-confirmation` | (DIFF-2) |
| PolarizationAnalyzer Family at n=2 | `AnalyzerArm` | `unknown-pending-confirmation` | (POL-2) |
| Sample-stage and pinhole Families | `SampleStage`, `Pinhole` | `unknown-pending-confirmation` | (STAGE-1) |
| Lakeshore cooling / heating ranges | `SampleTemperatureController`, `MagnetTemperatureController` | `unknown-pending-confirmation` | (TEMP-1) |
| Point-detector vs Sensor Family; channel map | `Detector`, `MagnetDetector` | `unknown-pending-confirmation` | (DET-1) |
| Magnet Family at n=2; fields, sweep, cryostat | `Electromagnet`, `HighFieldMagnet`, `ElectromagnetStage` | `unknown-pending-confirmation` | (MAG-1) |
| Vacuum extent and cooling supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
