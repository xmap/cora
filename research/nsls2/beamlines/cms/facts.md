# Extracted facts: CMS (11-BM)

Candidate device facts for `cms` (NSLS-II 11-BM, complex-materials scattering: SAXS/WAXS/MAXS, GISAXS/GIWAXS, and hard X-ray reflectivity). Candidates only; confirm every row before modeling. Source: the public `NSLS2/cms-profile-collection` (`startup/*.py`, read 2026-06; modules `10-motors`, `19-exp_shutter`, `20-area-detectors`, `25-scalers`, `26-IonChamber`, `27-Xspress3`, `30-beam-monitors`, `42-diodebox`, `51-linkam-stages`). Every value is carried `confirm` until CMS staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "NSLS-II twin of SMI; multi-detector scattering"
    CMS is the bending-magnet complex-materials scattering twin of SMI, with three Pilatus detectors on motorized stages (SAXS 2M, WAXS 800K, MAXS) plus the fleet's first hard X-ray reflectivity. Sample chambers and Linkam thermal stages support in-situ work.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PhotonShutter | Shutter | `XF:11BMA-PPS{PSh}` | (PPS shutter) | 11-BM-A | source | yes |
| ExperimentShutter | Shutter | `XF:11BM-ES{Shutter}` | fast exposure shutter (+ Psh_blade1/2) | 11-BM-B | source | yes |
| MultilayerMono | Monochromator | `XF:11BMA-OP{Mono:DMM-Ax:` | double-multilayer mono axes | 11-BM-A | source | yes |
| ToroidalMirror | Mirror | `XF:11BMA-OP{Mir:Tor-Ax:` | toroidal mirror axes | 11-BM-A | source | yes |
| WhiteBeamSlit | Slit | `XF:11BMA-OP{Slt:0` | t/b/i/o blades (Slt:0-Ax:T) | 11-BM-A | source | yes |
| Attenuator | Filter | `XF:11BMB-ES{ATT:1-Ax:` | attenuator axes | 11-BM-B | source | yes |
| SampleChamber | LinearStage | `XF:11BMB-ES{Chm:Smpl-Ax:` | sample chamber stages (Smpl/Smpl2/Smpl3) | 11-BM-B | sample | yes |
| GateChamber | LinearStage | `XF:11BMB-ES{Chm:Gate-Ax:` | gate chamber axes | 11-BM-B | sample | yes |
| Linkam | TemperatureController | `XF:11BM-ES:{LINKAM}` | thermal stage setpoint/ramp | 11-BM-B | sample | yes |
| PTASampleStage | LinearStage | `XF:11BMB-ES{PTA:Sample-Ax:` | laser-PTA sample stage | 11-BM-B | sample | yes |
| SAXSDetectorStage | LinearStage | `XF:11BMB-ES{Det:SAXS-Ax:` | SAXS detector positioning | 11-BM-B | detection | yes |
| WAXSDetectorStage | LinearStage | `XF:11BMB-ES{Det:WAXS-Ax:` | WAXS detector positioning | 11-BM-B | detection | yes |
| MAXSDetectorStage | LinearStage | `XF:11BMB-ES{Det:MAXS-Ax:` | MAXS detector positioning | 11-BM-B | detection | yes |
| DetectorStage | LinearStage | `XF:11BMB-ES{Det:Stg-Ax:` | general detector stage | 11-BM-B | detection | yes |
| Pilatus2M | Camera | `XF:11BMB-ES{Det:PIL2M}` | Pilatus 2M (SAXS) | 11-BM-B | detection | yes |
| Pilatus800K | Camera | `XF:11BMB-ES{Det:PIL800K}` | Pilatus 800K (WAXS) | 11-BM-B | detection | yes |
| Pilatus800K2 | Camera | `XF:11BMB-ES{Det:PIL800K2}` | second Pilatus 800K | 11-BM-B | detection | yes |
| SAXSBeamStop | BeamStop | `XF:11BMB-ES{BS:SAXS-Ax:` | SAXS beamstop axes | 11-BM-B | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:11BM-ES{Xsp:1}` | Xspress3 | 11-BM-B | detection | yes |
| IonChamberA | FluxMonitor | `XF:11BMA-BI{IM:1}` | ion monitor (optics) | 11-BM-A | detection | yes |
| IonChamberB | FluxMonitor | `XF:11BMB-BI{IM:2}` | ion monitor (endstation; IM:2-5) | 11-BM-B | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:11BMB-BI{BPM:1}` | beam position monitor | 11-BM-B | source | yes |
| EndstationMotionController | MotionController | `XF:11BMB-CT{MC:06}` | motion controller | 11-BM-B | sample | yes |

Device-level prefixes read verbatim from source (`Mono:DMM`, `Mir:Tor`, the three `Det:PIL*` Pilatus detectors + their `Det:SAXS/WAXS/MAXS` stages, the `LINKAM` block, `Chm:Smpl` chambers, `ATT:1` attenuator, `IM:1`/`IM:2` ion monitors).

## Role hints

- **Positioner**: mono, mirror, slit, attenuator, all sample/gate chambers, PTA stage, the four detector stages, beamstop.
- **Sensor**: two ion-chamber banks (IM:1 optics, IM:2-5 endstation), BPM, diode box.
- **Detector**: three Pilatus (2M/800K/800K2), Xspress3.
- **Regulator**: Linkam thermal stage (setpoint/ramp), the TemperatureController signature.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration, the layer CORA would replace. CMS is the SMI twin (the survey notes both as scattering twins); aligns with the existing `deployments/cms/` model.

## New-family watch

No new coining. Notes:
- **Linkam -> TemperatureController** (graduated, presents Regulator): CMS is another consumer (with CHX and PDF this batch reinforces the family broadly). Bind directly.
- **IonChamberA/B -> FluxMonitor** (graduated): bind directly.
- **Three Pilatus + stages -> Camera + LinearStage**: the multi-detector scattering layout is Assets, not new kinds.
- **BPM -> GenericProbe (loose)**: held DIAG-1.

## Deferred / absent

- **OceanOptics** (`52-oceanoptics.py`) spectrometer and **laser PTA** (`44-laserPTA.py`) partly mapped (PTA sample stage captured); the laser + optical spectrometer are deferred `OPT-1`.
- **DiodeBox** (`42-diodebox.py`) diagnostics partly mapped; deferred `DIAG-2`.
- The **bending-magnet source** referenced via beam-monitors; no standalone InsertionDevice (it is a bending magnet); carry `SRC-1`.
