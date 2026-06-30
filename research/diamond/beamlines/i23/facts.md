# Extracted facts: I23

Candidate device facts for `i23` (Diamond Light Source I23, long-wavelength macromolecular crystallography, in-vacuum). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i23.py`, read 2026-06). Every value is carried `confirm` until I23 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "Long-wavelength in-vacuum MX"
    I23 does MX at long wavelengths (low energy, for native-SAD phasing) with the sample and detector in vacuum. The dodal module carries the MX core: a six-axis goniometer, Pilatus detector on a 1D motion stage, Zebra gating, OAV viewing, and pin-tip detection. dodal PVs are `{beamline_prefix}-...` with `beamline_prefix` = **BL23I** (env-resolved).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| Goniometer | Goniometer | `BL23I-MO-GONIO-01:` | SixAxisGonio | sample | yes |
| SampleShutter | Shutter | `BL23I-EA-SHTR-01:` | MXZebraShutter | source | yes |
| PilatusDetector | Camera | `BL23I-EA-PILAT-01:` | PilatusDetector | detection | yes |
| DetectorMotion | LinearStage | `BL23I-EA-DET-01:Z` | Positioner1D[I23DetectorPositions] | detection | yes |
| Zebra | TimingController (?) | `BL23I-EA-ZEBRA-01:ZEBRA:` | Zebra | detection | yes |
| OAV | Camera | `BL23I-DI-OAV-01:` | OAVBeamCentreFile | sample | yes |
| PinTipDetection | GenericProbe (?) | (vision pin-tip find) | PinTipDetection | sample | yes |

Device-level prefixes read verbatim from source: `SixAxisGonio("{beamline_prefix}-MO-GONIO-01:")`, `MXZebraShutter("{beamline_prefix}-EA-SHTR-01:")`, `PilatusDetector("{beamline_prefix}-EA-PILAT-01:")`, `Positioner1D("{beamline_prefix}-EA-DET-01:Z")`, `Zebra(prefix="{beamline_prefix}-EA-ZEBRA-01:ZEBRA:")`, `OAVBeamCentreFile(prefix="{beamline_prefix}-DI-OAV-01:")`.

## Role hints

- **Positioner**: six-axis goniometer, detector 1D motion stage.
- **Detector**: Pilatus (diffraction), OAV (on-axis viewing camera).
- **Timing**: Zebra gates the rotation data collection.
- **Vision**: pin-tip detection (sample centring).

## Trust hints

dodal controls library; bluesky/GDA MX orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. Pure MX reuse:
- **SixAxisGonio -> Goniometer** (graduated via i03): I23 is a further Diamond MX consumer. Note the class is `SixAxisGonio` (vs i03/i04 `Smargon`), but the same Goniometer family, a variant within it. Bind directly.
- **PilatusDetector / OAV -> Camera** (graduated): bind directly.
- **DetectorMotion -> LinearStage**, **MXZebraShutter -> Shutter** (graduated): bind directly.
- **Zebra -> TimingController (?)**: the fleet-wide gating question.
- **PinTipDetection -> GenericProbe (loose)**: vision device.

## Deferred / absent

- **MONO-1 / OPTICS-1**: the DCM, mirrors, slits, and the long-wavelength in-vacuum beam-path optics are not in the read module; open questions.
- **VAC-1**: the in-vacuum sample/detector environment (i23's distinguishing feature) is not exposed as devices in dodal; an open question for staff.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
