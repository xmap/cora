# Extracted facts: I21

Candidate device facts for `i21` (Diamond Light Source I21, resonant inelastic X-ray scattering, soft X-ray RIXS). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i21.py`, read 2026-06). Every value is carried `confirm` until I21 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! warning "Partial scaffold: the RIXS spectrometer arm is absent"
    The public i21 dodal module carries the front end (PGM, EPU undulator with polarization, energy lookup), the sample environment (Lakeshore + manipulator), but NOT the **RIXS spectrometer arm** (the long, rotatable grating-spectrometer + CCD that disperses the inelastically-scattered soft X-rays, the instrument that makes i21 a RIXS beamline). Per the partial-scaffold discipline (i07/i16/i20-1), that is a named open question (SPEC-1), NOT invented. Consequence for the fleet: i21 does NOT trigger the SpectrometerArm rule-of-three; it stays at n=2 (NSLS-II six + ixs). dodal PVs are `{beamline_prefix}-...` with `beamline_prefix` = **BL21I** (env-resolved), insertion prefix = SR21I.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| PlaneGratingMono | GratingMonochromator | `BL21I-OP-PGM-01:` | PlaneGratingMonochromator | optics | yes |
| Undulator | InsertionDevice | `SR21I-MO-SERVC-01:` | UndulatorGap + UndulatorPhaseAxes (variable polarization) | source | yes |
| SampleManipulator | Manipulator | `BL21I-EA-SMPL-01:` | I21SampleManipulatorStage (+ ToolPointMotion uvw) | sample | yes |
| SampleTemperatureController | TemperatureController | `BL21I-EA-TCTRL-01:` | Lakeshore336 | sample | yes |
| Synchrotron | GenericProbe (?) | (Synchrotron machine status) | Synchrotron | source | yes |

Device-level prefixes read verbatim from source: `PlaneGratingMonochromator(prefix="{beamline_prefix}-OP-PGM-01:")`, `I21SampleManipulatorStage(prefix="{beamline_prefix}-EA-SMPL-01:")`, `Lakeshore336(prefix="{beamline_prefix}-EA-TCTRL-01:")`, the `UndulatorGap`/`UndulatorPhaseAxes(prefix="{insertion_prefix}-MO-SERVC-01:")`. The `uvw` factory wraps the manipulator in a `ToolPointMotion` (tool-point kinematics over the SMPL stage), not a separate PV.

## Role hints

- **Positioner**: PGM, sample manipulator (with tool-point motion kinematics).
- **Source**: EPU undulator (gap + phase = variable polarization, plus an energy lookup + polarisation control, important for RIXS dichroism).
- **Regulator**: Lakeshore 336 sample temperature (low-T RIXS).

## Trust hints

dodal controls library; bluesky/GDA orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. Reuse:
- **PlaneGratingMono -> GratingMonochromator** (graduated): another Diamond soft-X-ray consumer (with i05, i09).
- **SampleManipulator -> Manipulator** (graduated via esm): the RIXS sample manipulator; the `ToolPointMotion` is kinematics over it, not a new family. Bind Manipulator.
- **Lakeshore336 -> TemperatureController** (graduated), **EPU -> InsertionDevice** (catalog): bind directly.
- **SpectrometerArm**: NOT bound here, because the spectrometer arm is absent from dodal (SPEC-1). This is the key negative result: i21 was the candidate to take SpectrometerArm from n=2 to rule-of-three, but its arm is not in public source, so the family stays a WATCH at n=2.

## Deferred / absent (the headline)

- **SPEC-1**: the **RIXS spectrometer arm** (rotatable grating spectrometer + CCD detector dispersing the inelastically-scattered beam). The defining i21 instrument, absent from public dodal. When it lands it would be the 3rd SpectrometerArm consumer (with NSLS-II six + ixs), triggering that family's graduation review, alongside the EmissionSpectrometer / EnergyAnalyzer consolidation question.
- **DET-1**: the RIXS CCD detector (part of the arm).
- **OPTICS-1**: mirrors, slits, exit slit, beyond the PGM.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
