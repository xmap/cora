# Inventory

*The CORA Asset model for the operational core of P02 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared OH1 optics (the undulator, the DCM, the bendable HFM / VFM mirrors, the slits) and the two endstations (P02.1 powder / total scattering, P02.2 extreme conditions) with their sample stages, pressure cell, sample environment, and detectors. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p02/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P02 **coins no new Family**: it reuses the optics / motion / detector Families and the allowlisted-loose `PressureCell` Family (the 13-id-d precedent, now at its second consumer). The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P02` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P02` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p02-oh1 | undulator; gap axis; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p02-oh1 | DCM (bragg / parallel / perp + c2 crystal), ~60 keV; cut pending (OPT-1) |
| `HorizontalFocusingMirror` | `Device` | Mirror | p02-oh1 | bendable HFM (curvature / ellipticity / tilt / z + gp); coating pending (OPT-1) |
| `VerticalFocusingMirror` | `Device` | Mirror | p02-oh1 | bendable VFM (curvature / ellipticity / tilt / z + gp); coating pending (OPT-1) |
| `DefiningSlits` | `Device` | Slit | p02-oh1 | OH1 defining slits (slt1 + slt2) (OPT-1) |
| `OpticsStages` | `Device` | LinearStage | p02-oh1 | OH1 optics / instrument bank; grouped (OPT-1, GROUP-1) |
| `SampleStage` (P02.1) | `Device` | LinearStage | p02-1-powder | P02.1 sample banks (eh1a 48 + eh1b 16 axes); grouped (GROUP-1) |
| `SampleEnvironment` | `Device` | TemperatureController | p02-1-powder | Anton-Paar (Eurotherm 2604) + Eurotherm 2408 + Lakeshore 336 (TEMP-1) |
| `PilatusDetector` | `Device` | Camera | p02-1-powder | P02.1 Pilatus 1M; powder rings (DET-1) |
| `PerkinElmerDetector` | `Device` | Camera | p02-1-powder | P02.1 PerkinElmer flat-panel; high-Q PDF (DET-1) |
| `SampleStage` (P02.2) | `Device` | LinearStage | p02-2-extreme | P02.2 sample banks (eh2a 76 + eh2b 64 axes); grouped (GROUP-1) |
| `PressureCell` | `Device` | PressureCell (loose) | p02-2-extreme | diamond-anvil-cell high-pressure environment; 2nd consumer (PRESSURE-1) |
| `BeamMonitor` | `Device` | FluxMonitor | p02-2-extreme | CAEN-ELS AH501D picoammeter (DET-1) |
| `FluorescenceDetectors` | `Device` | EnergyDispersiveSpectrometer | p02-2-extreme | P02.2 MCA + SIS3302 fluorescence (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Slit`, `LinearStage`, `TemperatureController`, `Camera`, `FluxMonitor`, `EnergyDispersiveSpectrometer`. Allowlisted-loose Family reused: `PressureCell` (the 13-id-d precedent, now at its second consumer, `PRESSURE-1`). No new family is coined and nothing graduates. The CH1 / CH2 dummy stubs are noted, not modelled (`STUB-1`).

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + sample banks) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | mono, bendable-mirror attribute motors, CH dummy stubs (CTRL-1, STUB-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (OH1 + P02.1 + P02.2) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The DCM crystal cut, mirror coatings, CRL detail | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the motor banks | the `SampleStage` / `OpticsStages` Assets | `unknown-pending-confirmation` | (GROUP-1) |
| The diamond-anvil-cell membrane / load control | `PressureCell` | `unknown-pending-confirmation` | (PRESSURE-1) |
| The sample-environment sensor / setpoint handles | `SampleEnvironment` | `unknown-pending-confirmation` | (TEMP-1) |
| The detector roster, models, and P02.2 diffraction detector | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The CH1 / CH2 dummy-stub status | the controllers | `unknown-pending-confirmation` | (STUB-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
