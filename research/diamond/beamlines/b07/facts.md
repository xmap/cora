# Extracted facts: B07

Candidate device facts for `b07` (Diamond Light Source B07, VERSOX: versatile soft X-ray, ambient-pressure XPS / NEXAFS). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/b07.py`, `b07_1.py`, `b07_shared.py`, read 2026-06). Every value is carried `confirm` until B07 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "Two branches: B (BL07B) + C (BL07C)"
    B07 has two NAP-XPS endstation branches: branch B (`b07.py`, PGM + Specs analyser + two sample manipulators) and branch C (`b07_1.py`, PGM + a channel-cut mono + Specs analyser + manipulator). Both do ambient-pressure photoemission. dodal PVs are `{B_PREFIX}` = BL07B and `{C_PREFIX}` = BL07C (env-resolved). ElectronAnalyzer (graduated) applies to both analysers.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Branch | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PlaneGratingMonoB | GratingMonochromator | `BL07B-OP-PGM-01:` | PlaneGratingMonochromator | B | optics | yes |
| PlaneGratingMonoC | GratingMonochromator | `BL07C-OP-PGM-01:` | PlaneGratingMonochromator | C | optics | yes |
| ChannelCutMono | Monochromator | `BL07C-OP-CCM-01:` | ChannelCutMonochromator | C | optics | yes |
| ElectronAnalyserB | ElectronAnalyzer | `BL07B-EA-DET-01:CAM:` | SpecsDetector[LensMode, PsuMode] | B | detection | yes |
| ElectronAnalyserC | ElectronAnalyzer | `BL07C-EA-DET-01:CAM:` | SpecsDetector[LensMode, PsuMode] | C | detection | yes |
| SampleManipulatorB52 | Manipulator | `BL07B-EA-SM-52:` | B07SampleManipulator52B | B | sample | yes |
| SampleManipulatorB21 | Manipulator | `BL07B-EA-SM-21:` | XYZAzimuthStage (azimuth_infix ROTY) | B | sample | yes |
| SampleManipulatorC | Manipulator | `BL07C-EA-SM-01:` | XYZAzimuthPolarStage | C | sample | yes |
| HutchShutter | Shutter | (HutchShutter) | HutchShutter | both | source | yes |
| Synchrotron | GenericProbe (?) | (machine status) | Synchrotron | both | source | yes |

Device-level prefixes read verbatim from source: `PlaneGratingMonochromator(prefix="{B_PREFIX}-OP-PGM-01:" / "{C_PREFIX}-OP-PGM-01:")`, `ChannelCutMonochromator(prefix="{C_PREFIX}-OP-CCM-01:")`, the two `SpecsDetector(prefix="...-EA-DET-01:CAM:")`, the three sample manipulators (`-EA-SM-52:`, `-EA-SM-21:`, `-EA-SM-01:`).

## Role hints

- **Positioner**: two PGMs, channel-cut mono, three sample manipulators.
- **Detector / analyzer**: two SPECS hemispherical electron analysers (one per branch).

## Trust hints

dodal controls library; bluesky/GDA orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. Reuse, reinforcing the cross-vendor ElectronAnalyzer picture:
- **SpecsDetector x2 -> ElectronAnalyzer** (graduated): B07 adds two more SPECS analyser consumers. Across Diamond now (i05 MBS, i09 SPECS+VGScienta, b07 SPECS x2), ElectronAnalyzer is firmly multi-beamline + multi-vendor. Bind directly.
- **PlaneGratingMono -> GratingMonochromator** (graduated): two more consumers.
- **ChannelCutMono -> Monochromator** (graduated): the channel-cut is a Monochromator variant; bind Monochromator (confirm vs a dedicated channel-cut treatment, single use).
- **Sample manipulators -> Manipulator** (graduated via esm): photoemission orientation stages (azimuth/polar), NOT MX Goniometer. Note three distinct manipulator classes across the two branches, all the Manipulator family.

## Deferred / absent

- The NAP (near-ambient-pressure) cell / gas system, mirrors, slits, and beam diagnostics are not in the read modules; `OPTICS-1` / `NAP-1`.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
