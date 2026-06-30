# Extracted facts: B16

Candidate device facts for `b16` (Diamond Light Source B16, Test beamline: optics and detector testing / metrology). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/b16.py`, read 2026-06). Every value is carried `confirm` until B16 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "Test beamline; minimal dodal device set"
    B16 is Diamond's test beamline, used for optics development, detector characterisation, and metrology rather than a fixed science program. The public dodal module exposes a small, generic device set: Attocube piezo positioners, an area detector, and a simulation stage. There is no fixed mono / sample / spectrometer because the configuration changes per experiment. dodal PVs are `{beamline_prefix}-...` with `beamline_prefix` = **BL16B** (env-resolved).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| AttocubeLinear1 | LinearStage | `BL16B-EA-ECC-03:ACT0` | Motor | sample | yes |
| AttocubeLinear2 | LinearStage | `BL16B-EA-ECC-03:ACT1` | Motor | sample | yes |
| AttocubeLinear3 | LinearStage | `BL16B-EA-ECC-03:ACT2` | Motor | sample | yes |
| AttocubeRotation1 | RotaryStage | `BL16B-EA-ECC-02:ACT2` | Motor | sample | yes |
| AreaDetector | Camera | `BL16B-EA-FDS-02:` | AreaDetector (software-triggered TIFF) | detection | yes |
| SimStage | LinearStage | `BL16B-MO-SIM-01:` | XYZStage (simulation) | sample | yes |

Device-level prefixes read verbatim from source: `Motor("{beamline_prefix}-EA-ECC-03:ACT0" / "ACT1" / "ACT2")`, `Motor("{beamline_prefix}-EA-ECC-02:ACT2")`, `software_triggered_tiff_area_detector("{beamline_prefix}-EA-FDS-02:")`, `XYZStage("{beamline_prefix}-MO-SIM-01:")`.

## Role hints

- **Positioner**: the Attocube ECC piezo actuators (three linear ACT0-2 + one rotation), the sim stage.
- **Detector**: a software-triggered TIFF area detector (the generic test detector).

## Trust hints

dodal controls library; bluesky/GDA orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. Generic devices, all graduated families:
- **Attocube Motors -> LinearStage / RotaryStage** (graduated): the ECC piezo actuators are positioners; the three ACT linear axes bind LinearStage, the rotation binds RotaryStage. No per-vendor family (matches the HXN nanofocus discipline: piezo controllers are motion topology, not new kinds).
- **AreaDetector -> Camera** (graduated): the software-triggered TIFF detector.
- **SimStage -> LinearStage**: a simulation stage (note `MO-SIM-01:`); a real device handle but used for testing.

## Deferred / absent

- B16's per-experiment optics-under-test, mono, and metrology instruments are not fixed in dodal (by the nature of a test beamline); the module exposes only the generic positioners + detector. This is faithful: B16 is modellable only as its generic test kit, not a fixed science instrument set.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
