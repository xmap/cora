# Inventory

*The CORA Asset model for the operational core of P09 modelled today: the planned device tree and what still needs confirming.*

This cut models the MONO hutch (the undulator, the DCM, the mirrors, the CRL, the slit, the absorber, the resonant-scattering instrument, the fluorescence detectors), the DIF diffraction hutch, and the MAG high-field magnetism endstation. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p09/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P09 **coins no new Family**: it binds the catalog `PhaseRetarder` and `PolarizationAnalyzer` Families (the analyzer earned across 4-ID / i10 / ID32 / P09, presenting Positioner) and is a further consumer of the graduated catalog `Magnet` Family the APS 4-ID deployment introduced (earned across 4-ID + i10-1 + ID32), reusing the optics / motion / detector Families otherwise. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P09` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P09` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p09-mono | undulator; gap axis; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p09-mono | DCM (DCM_BRAGG / energyfmb + coupled mnchrmtr); cut pending (OPT-1) |
| `Mirror1` | `Device` | Mirror | p09-mono | first mirror (pitch / x / y / yaw, spk); coating pending (OPT-1) |
| `Mirror2` | `Device` | Mirror | p09-mono | second mirror (bender + pitch / x / y / yaw); coating pending (OPT-1) |
| `CompoundRefractiveLens` | `Device` | Transfocator | p09-mono | CRL control (lensctrl) (OPT-1) |
| `DefiningSlit` | `Device` | Slit | p09-mono | MONO defining slit (G1, Galil) |
| `Absorber` | `Device` | Filter | p09-mono | MONO beam absorber (absbox -> Filter) (OPT-1) |
| `OpticsStages` | `Device` | LinearStage | p09-mono | MONO optics / instrument bank (p09/motor/exp, ~98 axes); grouped (GROUP-1) |
| `PhaseRetarder` | `Device` | PhaseRetarder (catalog) | p09-mono | polarization phase-retarder circles + AttoCube fine axes (POL-1) |
| `PolarizationAnalyzer` (MONO) | `Device` | PolarizationAnalyzer (catalog) | p09-mono | scattered-beam analyzer (POL-2) |
| `Goniometer` (MONO) | `Device` | Goniometer | p09-mono | MONO six-circle (E6C) diffractometer; not the Diffractometer Assembly (DIFF-1) |
| `SampleTemperature` (MONO) | `Device` | TemperatureController | p09-mono | CryoCon 32 + Lakeshore 336 / 340 + LSCI (TEMP-1) |
| `PerkinElmerDetector` | `Device` | Camera | p09-mono | PerkinElmer flat-panel area detector (DET-1) |
| `PilatusDetector` (MONO) | `Device` | Camera | p09-mono | MONO Pilatus 300k (DET-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | p09-mono | SIS3302 digitizer (ROI explosion grouped) + MCA (DET-1) |
| `Goniometer` (DIF) | `Device` | Goniometer | p09-dif | DIF six-circle diffractometer (OMS VME58); not the Assembly (DIFF-1) |
| `SampleStage` (DIF) | `Device` | LinearStage | p09-dif | DIF sample bank (p09/motor/dif, ~69 axes); grouped (GROUP-1) |
| `Magnet` | `Device` | Magnet | p09-mag | 14 T superconducting sample-environment magnet; graduated Family, a further consumer (MAG-1) |
| `Goniometer` (MAG) | `Device` | Goniometer | p09-mag | MAG six-circle diffractometer + mu circle (DIFF-1) |
| `SampleHexapod` | `Device` | Hexapod | p09-mag | MAG sample hexapod (hexa_*) (SAMPLE-1) |
| `SamplePiezo` (MAG) | `Device` | LinearStage | p09-mag | MAG PI E-710 scan + E-725 sample piezos (SAMPLE-1) |
| `PolarizationAnalyzer` (MAG) | `Device` | PolarizationAnalyzer (catalog) | p09-mag | MAG scattered-beam analyzer (POL-2) |
| `Absorber` (MAG) | `Device` | Filter | p09-mag | MAG beam absorber (OPT-1) |
| `SampleTemperature` (MAG) | `Device` | TemperatureController | p09-mag | MAG Lakeshore 336 / 340 (TEMP-1) |
| `PilatusDetector` (MAG) | `Device` | Camera | p09-mag | MAG Pilatus 100k (DET-1) |
| `AndorCamera` | `Device` | Camera | p09-mag | MAG Andor camera (Lima) (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Transfocator`, `Slit`, `Filter`, `LinearStage`, `Goniometer`, `TemperatureController`, `Hexapod`, `Camera`, `EnergyDispersiveSpectrometer`, `PhaseRetarder` (the 4-ID precedent, P09 is a consumer in the 4-ID / P09 / P22 rule-of-three, `POL-1`), `PolarizationAnalyzer` (graduated across 4-ID / i10 / ID32 / P09, `POL-2`), `Magnet` (graduated across 4-ID + i10-1 + ID32; presents `Regulator`, a further consumer, `MAG-1`). No new family is coined here.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 / VME58 steppers (optics / diffractometer / sample banks) (CTRL-1) |
| `GalilSlitControllers` | MotionController | Tango_galildmcslit | Galil DMC slit controllers (MONO slit) (CTRL-1) |
| `PiezoControllers` | MotionController | Tango_piezo | PI + AttoCube fine-stage controllers (CTRL-1) |
| `HexapodControllers` | MotionController | Tango_hexapod | hexapod controllers (MAG hexapod) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | mono / mirrors / coupled axes (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (MONO + DIF + MAG) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The DCM crystal cut, mirror coatings, CRL detail | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The diffractometer circle counts and detector arms | the `Goniometer` Assets | `unknown-pending-confirmation` | (DIFF-1) |
| The per-axis roles of the motor banks | `OpticsStages`, `SampleStage` (DIF) | `unknown-pending-confirmation` | (GROUP-1) |
| The phase-retarder / analyzer detail | `PhaseRetarder`, `PolarizationAnalyzer` | `unknown-pending-confirmation` | (POL-1) |
| The 14 T magnet field and control detail | `Magnet` | `unknown-pending-confirmation` | (MAG-1) |
| The MAG sample hexapod / piezo detail | `SampleHexapod`, `SamplePiezo` (MAG) | `unknown-pending-confirmation` | (SAMPLE-1) |
| The cryo / heater sensor / setpoint handles | the `SampleTemperature` Assets | `unknown-pending-confirmation` | (TEMP-1) |
| The detector roster, models, SIS3302 channel count | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The shared Lambda host and the excluded P07 device | the detector pool | `unknown-pending-confirmation` | (HOST-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies (incl. magnet He) | the supplies | `unknown-pending-confirmation` | (SUP-1) |
