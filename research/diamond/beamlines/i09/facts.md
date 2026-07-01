# Extracted facts: I09

Candidate device facts for `i09` (Diamond Light Source I09, atomic and electronic structure: HAXPES + soft-X-ray photoemission, a dual hard/soft-source beamline). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i09.py`, `i09_1.py`, `i09_2.py`, + `_shared` modules, read 2026-06). Every value is carried `confirm` until I09 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "Dual source: hard (I = BL09I) + soft (J = BL09J)"
    I09 uniquely combines a hard X-ray branch (DCM, source prefix `I_PREFIX` = BL09I / SR09I) and a soft X-ray branch (PGM, `J_PREFIX` = BL09J / SR09J), with a `DualEnergySource` / `SourceSelector` switching between them. It carries TWO electron analysers: a SPECS (hard, DET-02) and a VG Scienta (soft, DET-01). The `BL09L` prefix on the shared Lakeshore is the lab/shared subdomain. ElectronAnalyzer (graduated) applies to both analysers.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Branch | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| DCM | Monochromator | `BL09I-MO-DCM-01:` | DoubleCrystalMonochromatorWithDSpacing | hard | source | yes |
| PGM | GratingMonochromator | `BL09J-MO-PGM-01:` | PlaneGratingMonochromator | soft | source | yes |
| HardUndulator | InsertionDevice | `SR09I-MO-SERVC-01:` | UndulatorInMm | hard | source | yes |
| SoftUndulator | InsertionDevice | `SR09J-MO-SERVC-01:` | UndulatorInMm | soft | source | yes |
| DualEnergySource | GenericProbe (?) | (DualEnergySource + SourceSelector) | DualEnergySource | both | source | yes |
| SpecsAnalyser | ElectronAnalyzer | `BL09I-EA-DET-02:CAM:` | SpecsDetector | hard | detection | yes |
| ScientaAnalyser | ElectronAnalyzer | `BL09J-EA-DET-01:CAM:` | VGScientaDetector | soft | detection | yes |
| HardSampleManipulator | Manipulator | `BL09I-MO-SMPM-01:` | XYZAzimuthPolarStage | hard | sample | yes |
| SoftSampleManipulator | Manipulator | `BL09J-MO-HSMPM-01:` | XYZAzimuthTiltPolarStage | soft | sample | yes |
| SampleTemperatureController | TemperatureController | `BL09L-VA-LAKE-01:` (+ `-EA-TCTRL-01:`) | Lakeshore336 | shared | sample | yes |
| DualFastShutter | Shutter | (DualFastShutter) | DualFastShutter | both | source | yes |
| HutchShutter | Shutter | (HutchShutter) | HutchShutter | both | source | yes |
| IntensityProtection | GenericProbe (?) | (IntensityProtection signal) | SignalRW[IntensityProtection] | both | source | yes |
| Synchrotron | GenericProbe (?) | (Synchrotron machine status) | Synchrotron | both | source | yes |

Device-level prefixes read verbatim from source: `DCM("{I_PREFIX.beamline_prefix}-MO-DCM-01:")`, `PlaneGratingMonochromator(prefix="{J_PREFIX.beamline_prefix}-MO-PGM-01:")`, `SpecsDetector(prefix="{beamline_prefix}-EA-DET-02:CAM:")`, `VGScientaDetector(prefix="{I_PREFIX.beamline_prefix}-EA-DET-01:CAM:")`, the SMPM/HSMPM manipulators, `Lakeshore336(prefix="BL09L-VA-LAKE-01:")`, the two `UndulatorInMm(prefix="{insertion_prefix}-MO-SERVC-01:")`.

## Role hints

- **Positioner**: DCM, PGM, both sample manipulators.
- **Source**: two undulators (hard + soft) with a DualEnergySource/SourceSelector switching mechanism.
- **Detector / analyzer**: SPECS (hard HAXPES) + VG Scienta (soft XPS) hemispherical electron analysers.
- **Regulator**: Lakeshore 336 sample temperature.

## Trust hints

dodal controls library; bluesky/GDA orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. Strong reuse, and a notable cross-vendor confirmation:
- **SpecsDetector + VGScientaDetector -> ElectronAnalyzer** (graduated via NSLS-II esm/ios/sst): i09 binds TWO more analysers, from TWO more vendors (SPECS, VG Scienta), on one beamline. With i05 (MB Scientific), Diamond now confirms ElectronAnalyzer across four vendors total. Bind both directly.
- **DCM -> Monochromator**, **PGM -> GratingMonochromator** (graduated), **both undulators -> InsertionDevice**, **Lakeshore336 -> TemperatureController** (graduated): bind directly.
- **Sample manipulators -> Manipulator** (graduated via esm): photoemission sample orientation (azimuth/polar/tilt), NOT MX Goniometer. Same discrimination as i05.
- **DualEnergySource / SourceSelector / IntensityProtection -> GenericProbe (loose)**: the dual-source switching logic; confirm whether SourceSelector warrants its own family if it recurs (single beamline so far, do not coin).

## Deferred / absent

- The hard/soft optical mirrors, slits, and detailed beam diagnostics beyond what the factories expose are partly out of the read modules; `OPTICS-1`.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
- Confirm the `BL09L` shared subdomain (Lakeshore) vs the `BL09I`/`BL09J` branch prefixes with staff.
