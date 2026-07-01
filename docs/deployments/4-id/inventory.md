# Inventory

*The CORA Asset model for the operational core of 4-ID modelled today: the planned device tree and what still needs confirming.*

This cut models the 4-ID-A optics spine and the per-station optics, diffractometers, sample environment, and detectors of 4-ID-B / G / H; the Raman station and the peripheral electronics are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/4-id/beamline.yaml) descriptor that the Source page renders from.

Devices bind to a catalog [Family](../../catalog/families.md) where one fits. 4-ID's `Laser` binds the graduated catalog `Laser` Family (an optical sample laser earned across 4-ID / LCLS-MFX / Alvra / Bernina / Cristallina, one Family spanning pump-probe and alignment/reference lasers as a per-Asset purpose); the `PhaseRetarder` phase retarders now bind the graduated catalog `PhaseRetarder` Family (earned across 4-ID / P09 / P22, presenting the `Positioner` Role); the analyzer now binds the graduated catalog `PolarizationAnalyzer` Family (a polarization-analysis positioner, earned across 4-ID / i10 / ID32 / P09, presenting the `Positioner` Role); the `Transfocator` CRL now binds the graduated catalog `Transfocator` Family (a CRL focusing optic, earned across eight deployments), the beam-position monitors bind the graduated catalog `BeamPositionMonitor` Family (presents the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux), the `TemperatureController` controllers and the `Magnet` sample magnets bind catalog Families (`TemperatureController` graduated on the Diamond i22/i03/i11 rule-of-three, `Magnet` on the 4-ID + i10-1 + ID32 rule-of-three, both presenting the `Regulator` Role), and the diffractometer devices bind the catalog `Goniometer` Family (the graduation register is on [Model](model.md#loose-family-graduation)). Unlike the design-phase scaffolds, the control handles are filled from the beamline config; no vendor Models are bound.

## The Asset tree

Root Asset `4-ID` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`. The Raman station and the peripheral electronics are not in this tree (deferred).

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `4-ID` | `Unit` | (root) | - | bound to the APS Site; four hutches |
| `Undulators` | `Device` | InsertionDevice | 4-ID-A | undulator pair (`S04ID:`) |
| `PhaseRetarder_1/2/3` | `Device` | PhaseRetarder | 4-ID-A | diamond phase retarders, energy-tracking (POL-1) |
| `Monochromator` | `Device` | Monochromator | 4-ID-A | vertical DCM (`4idVDCM:`) with crystal-select (MONO-1) |
| `WhiteBeamSlit` / `MonoSlit` | `Device` | Slit | 4-ID-A | VDCM-crate slits |
| `DiamondWindow` | `Device` | Window | 4-ID-B | 2-axis diamond window |
| `ToroidalMirror` / `HHLMirror` | `Device` | Mirror | 4-ID-B | toroidal pre-focus and HHL bendable mirror (OPT-1) |
| `Transfocator` | `Device` | Transfocator | 4-ID-G | CRL transfocator (OPT-2) |
| `KBMirror_B/G/H` | `Device` | Mirror | 4-ID-B/G/H | per-station KB focusing mirrors (OPT-3) |
| `Filter_B/G/H` | `Device` | Filter | 4-ID-B/G/H | per-station attenuator banks |
| `Diffractometer_Euler` | `Device` | Goniometer | 4-ID-G | Huber Eulerian cradle; goniometer of the Diffractometer Assembly (DIFF-1) |
| `Diffractometer_HighPressure` | `Device` | Goniometer | 4-ID-G | high-pressure diffractometer; goniometer of the Diffractometer Assembly (DIFF-1) |
| `PolarizationAnalyzer` | `Device` | PolarizationAnalyzer (catalog) | 4-ID-B | analyzer crystal stage (POL-2) |
| `Magnet_2T_B` / `Magnet_2T_E` | `Device` | Magnet | 4-ID-B | 2 T sample magnets (MAG-1) |
| `Magnet_9T_H` | `Device` | Magnet | 4-ID-H | high-field magnet (MAG-1) |
| `Magnet_Kepco_G` | `Device` | Magnet | 4-ID-G | Kepco electromagnet; station a guess (TOPO-3, MAG-1) |
| `TemperatureController_336/340` | `Device` | TemperatureController | 4-ID-G | LakeShore controllers; catalog Family, presents Regulator (TEMP-1) |
| `SampleTable_B/H` | `Device` | Table | 4-ID-B/H | sample positioning tables |
| `PumpProbeLaser` | `Device` | Laser | 4-ID-H | Ventus laser (SAMPLE-1) |
| `SampleSlit_B/G/H` | `Device` | Slit | 4-ID-B/G/H | per-station sample slits |
| `Eiger1M` | `Device` | Camera | 4-ID-G | Eiger 1M area detector (DET-1) |
| `FlagCamera_HHL/Mono` | `Device` | Camera | 4-ID-A | beam-view flag cameras |
| `VortexFluorescence` | `Device` | BeamPositionMonitor | 4-ID-G | SGZ Vortex; classification a placeholder (DET-2, TOPO-3) |
| `XBPM_G/H`, `Sydor_G/H`, `TetrAMM_B` | `Device` | BeamPositionMonitor | 4-ID-B/G/H | beam-position / intensity monitors (BPM-1) |
| `Scaler_1/2` | `Device` | GenericProbe | 4-ID-B | CTR8 scaler channels |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Slit`, `Window`, `Mirror`, `Filter`, `Table`, `Camera`, `GenericProbe`, `Transfocator` (the CRL focusing optic), `Goniometer` (the diffractometer sample circles), `PhaseRetarder` (the diamond phase retarders), `PolarizationAnalyzer` (the polarization-analysis positioner), `Magnet` (the sample magnets, graduated on the 4-ID + i10-1 + ID32 rule-of-three, presents `Regulator`), `BeamPositionMonitor` (the beam-position monitors, a catalog Family presenting the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux), and `Laser` (the optical sample laser, a catalog Family spanning pump-probe and alignment/reference lasers as a per-Asset purpose, earned across 4-ID / LCLS-MFX / Alvra / Bernina / Cristallina). `Transfocator`, `PhaseRetarder`, `PolarizationAnalyzer`, `TemperatureController`, `Magnet`, `BeamPositionMonitor`, and `Laser` recurred too and have since graduated to catalog Families (`TemperatureController` and `Magnet` present `Regulator`; `PhaseRetarder` presents `Positioner`, earned across 4-ID / P09 / P22; `PolarizationAnalyzer` presents `Positioner`, earned across 4-ID / i10 / ID32 / P09; `BeamPositionMonitor` presents `Sensor`; `Laser` presents no existing Role). The graduation plan is on [Model](model.md#loose-family-graduation).

## Pending confirmations

Every value below is a config-read value or an inference awaiting the 4-ID team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Beam topology (stations in series vs branched) | the root and optics spine | `unknown-pending-confirmation` | (TOPO-1) |
| Raman station devices | a possible fifth enclosure | `unknown-pending-confirmation` | (TOPO-2) |
| Vortex and Kepco station assignment | `VortexFluorescence`, `Magnet_Kepco_G` | `unknown-pending-confirmation` | (TOPO-3) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| Hutch PSS permit signals | the four enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Undulator types and periods | `Undulators` | `unknown-pending-confirmation` | (SRC-1) (SRC-2) |
| Monochromator energy model | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | `ToroidalMirror`, `HHLMirror`, KB mirrors | `unknown-pending-confirmation` | (OPT-1) (OPT-3) |
| Transfocator lens spec | `Transfocator` | `unknown-pending-confirmation` | (OPT-2) |
| Phase-retarder specs and state model | `PhaseRetarder_1/2/3` | `unknown-pending-confirmation` | (POL-1) |
| Polarization analyzer spec | `PolarizationAnalyzer` | `unknown-pending-confirmation` | (POL-2) |
| Diffractometer circle geometry | the two diffractometers | `unknown-pending-confirmation` | (DIFF-1) (DIFF-2) |
| Magnet fields and handles | the four magnets | `unknown-pending-confirmation` | (MAG-1) |
| Temperature-controller channels | `TemperatureController_336/340` | `unknown-pending-confirmation` | (TEMP-1) |
| Laser model or hazard treatment | `PumpProbeLaser` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Detector camera model | `Eiger1M` | `unknown-pending-confirmation` | (DET-1) |
| Vortex classification | `VortexFluorescence` | `unknown-pending-confirmation` | (DET-2) |
| Beam-position vs intensity monitor split | the BPM Assets | `unknown-pending-confirmation` | (BPM-1) |
| Cryogen and process-gas supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
