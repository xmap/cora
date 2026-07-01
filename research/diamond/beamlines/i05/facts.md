# Extracted facts: I05

Candidate device facts for `i05` (Diamond Light Source I05, angle-resolved photoemission spectroscopy: ARPES + nano-ARPES). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i05.py`, `i05_1.py`, `i05_shared.py`, read 2026-06). Every value is carried `confirm` until I05 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "Two branches; PV root BL05I"
    I05 has two endstation branches sharing the optics: the main ARPES station (`i05.py`, analyser DET-02) and the nano-ARPES station (`i05_1.py`, analyser DET-04). Shared optics (PGM, mirrors, undulator) are in `i05_shared.py`. dodal PVs are `{beamline_prefix}-XX-YYY-NN:` with `beamline_prefix` = **BL05I** (env-resolved), insertion prefix = SR05I. This is CORA's first Diamond photoemission beamline; the ElectronAnalyzer family (graduated via NSLS-II esm/ios/sst) applies.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, the dodal class as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | dodal class | Branch | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PlaneGratingMono | GratingMonochromator | `BL05I-OP-PGM-01:` | PlaneGratingMonochromator | shared | source | yes |
| M1CollimatingMirror | Mirror | `BL05I-OP-COL-01:` | XYZPitchYawRollStage | shared | source | yes |
| M3M6SwitchingMirror | Mirror | `BL05I-OP-SWTCH-01:` | XYZPiezoSwitchingMirror | shared | source | yes |
| M4M5SwitchingMirror | Mirror | `BL05I-OP-RFM-01:` | XYZSwitchingMirror | main | source | yes |
| UndulatorGap | InsertionDevice | `SR05I-MO-SERVC-01:` | UndulatorGap | shared | source | yes |
| UndulatorPhase | InsertionDevice | `SR05I-MO-SERVC-01:` | UndulatorLockedPhaseAxes (variable polarization) | shared | source | yes |
| SampleGoniometer | Manipulator | (I05Goniometer; ARPES sample manipulator) | I05Goniometer | main | sample | yes |
| NanoSampleManipulator | Manipulator | `BL05I-EA-SM-01:` | XYZAzimuthPolarDefocusStage | nano | sample | yes |
| SampleTemperatureController | TemperatureController | `BL05I-EA-TCTRL-02:` | Lakeshore336 | main | sample | yes |
| AnalyserSlits | Slit | (EntranceSlitInformationDevice) | EntranceSlitInformationDevice | both | source | yes |
| ElectronAnalyserMain | ElectronAnalyzer | `BL05I-EA-DET-02:CAM:` | MbsDetector[LensMode, PassEnergy] | main | detection | yes |
| ElectronAnalyserNano | ElectronAnalyzer | `BL05I-EA-DET-04:CAM:` | MbsDetector[LensMode, PassEnergy] | nano | detection | yes |
| HutchShutter | Shutter | (HutchShutter) | HutchShutter | both | source | yes |
| Synchrotron | GenericProbe (?) | (Synchrotron machine status) | Synchrotron | shared | source | yes |

Device-level prefixes read verbatim from source: `PlaneGratingMonochromator(prefix="...-OP-PGM-01:")`, the COL/SWTCH/RFM mirrors, `Lakeshore336(prefix="...-EA-TCTRL-02:")`, the two `MbsDetector(prefix="...-EA-DET-02:CAM:" / "...-EA-DET-04:CAM:")` analysers, `XYZAzimuthPolarDefocusStage(prefix="...-EA-SM-01:")`, `UndulatorGap/UndulatorLockedPhaseAxes(prefix="{insertion_prefix}-MO-SERVC-01:")`.

## Role hints

- **Positioner**: PGM, all mirrors, the sample goniometer/manipulator (both branches), analyser slits.
- **Source**: EPU undulator (gap + locked-phase axes = variable polarization, a controllable axis for ARPES dichroism).
- **Detector / analyzer**: two MB Scientific hemispherical electron analysers (main + nano), parameterized by LensMode + PassEnergy.
- **Regulator**: Lakeshore 336 sample temperature controller (cryo-ARPES), the settable-setpoint signature.

## Trust hints

dodal controls library; Diamond runs bluesky/GDA over it. The orchestration CORA's EdgeConductor would conduct over. Trust modeled CORA-native.

## New-family watch

No new coining. Clean reuse, and it extends a graduated family to a new facility:
- **MbsDetector -> ElectronAnalyzer** (graduated via NSLS-II esm/ios/sst): I05 is the FIRST Diamond consumer, confirming the family generalizes across facilities (MB Scientific here vs Scienta/SPECS at NSLS-II). Bind directly. The LensMode/PassEnergy parameterization is the analyser's scan config, not new device kinds.
- **PlaneGratingMono -> GratingMonochromator** (graduated via NSLS-II csx): first Diamond consumer; bind directly.
- **Lakeshore336 -> TemperatureController** (graduated): another Regulator consumer.
- **I05Goniometer / nano stage -> Manipulator** (graduated via NSLS-II esm): the ARPES sample manipulator (azimuth/polar/defocus) is the Manipulator family, NOT the MX Goniometer (different contract: photoemission sample orientation vs crystallography cradle). Confirm the binding; this is the key naming discrimination for i05.
- **EPU -> InsertionDevice** (catalog): variable polarization; bind directly.

## Deferred / absent

- The `I05Goniometer` class wraps the main-branch sample manipulator; its exact PV root was not a literal in the read lines (constructed inside the class). Confirm the manipulator PV with staff (`MANIP-1`); the nano-branch manipulator PV (`-EA-SM-01:`) is verbatim.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
