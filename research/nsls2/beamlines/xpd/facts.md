# Extracted facts: XPD (28-ID)

Candidate device facts for `xpd` (NSLS-II 28-ID, high-energy X-ray powder diffraction and total scattering / PDF). Candidates only; confirm every row before modeling. Source: the public `NSLS2/xpd-profile-collection` (`startup/*.py`, read 2026-06; modules `10-motors`, `11-temperature-controller`, `12-rga`, `15-optics`, `16-electrometer`, `18-ion-chamber`, `20-scalers`, `25-QEPro`, `26-pump_ultra`, `28-Lights_shutter`). Every value is carried `confirm` until XPD staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Diamond i11 / i15-1 twin; deep in-situ environment"
    XPD is the NSLS-II powder/total-scattering twin of Diamond i11 and i15-1. Like PDF it carries a deep in-situ sample-environment stack (LS335 cryostat, CS800 cryostream, Linkam, multiple Env controllers, syringe pumps). It uses a double-Laue mono (DLM) for high-energy total scattering plus an HRM mono.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| ExperimentShutter | Shutter | `XF:28IDC-ES:1{Sh2:Exp-Ax:` | motorized exposure shutter | 28-ID-C | source | yes |
| DoubleLaueMono | Monochromator | `XF:28IDA-OP:1{Mono:DLM-C:1-Ax:` | crystal 1 + crystal 2 (`DLM-C:2`); high-energy total scattering | 28-ID-A | optics | yes |
| HighResMono | Monochromator | `XF:28IDC-OP:1{Mono:HRM-Ax:` | HRM mono axes | 28-ID-C | optics | yes |
| VerticalFocusingMirror | Mirror | `XF:28IDA-OP:1{Mir:VFM-Ax:` | VFM axes | 28-ID-A | optics | yes |
| MonoBeamSlit1 | Slit | `XF:28IDA-OP:1{Slt:MB1` | blade axes | 28-ID-A | optics | yes |
| MonoBeamSlit2 | Slit | `XF:28IDC-OP:1{Slt:MB2` | blade axes | 28-ID-C | optics | yes |
| Filter1 | Filter | `XF:28IDA-OP:2{Fltr:1-Ax:` | filter axes (+ Fltr:6, Fltr) | 28-ID-A | optics | yes |
| Pinhole | Slit (?) | `XF:28IDC-ES:1{PinHole:XRD-Ax:` | XRD pinhole positioning | 28-ID-C | optics | yes |
| SampleStage | LinearStage | `XF:28IDC-ES:1{Stg:Smpl2-Ax:` | sample stage axes | 28-ID-C | sample | yes |
| SampleArray | LinearStage | `XF:28IDC-ES:1{SampArray-Ax:` | multi-sample array | 28-ID-C | sample | yes |
| MADStage | LinearStage | `XF:28IDC-ES:1{MAD:DMS-Ax:` | MAD detector-motion stage | 28-ID-C | sample | yes |
| Diffractometer1 | Diffractometer (?) | `XF:28IDC-ES:1{Dif:1-Ax:` | diffraction stage 1 | 28-ID-C | sample | yes |
| Diffractometer2 | Diffractometer (?) | `XF:28IDC-ES:1{Dif:2-Ax:` | diffraction stage 2 | 28-ID-C | sample | yes |
| CameraMount | LinearStage | `XF:28IDD-ES:2{Cam:Mnt-Ax:` | camera mount axes | 28-ID-D | detection | yes |
| DetectorStack | LinearStage | `XF:28IDD-ES:2{Stg:Stack-Ax:` | detector stack axes | 28-ID-D | detection | yes |
| PerkinElmer1 | Camera | `XF:28IDC-ES:1{Det:PE1-Ax:` | Perkin-Elmer flat-panel (+ positioning) | 28-ID-C | detection | yes |
| ScintillationDetector | GenericProbe (?) | `XF:28IDC-ES:1{Det:SC2}` | scintillation counter | 28-ID-C | detection | yes |
| LakeshoreCryostat | TemperatureController | `XF:28IDC-ES1:LS335:{CryoStat}` | LS335 cryostat | 28-ID-C | sample | yes |
| CS800Cryostream | TemperatureController | `XF:28IDC-ES:1{CS:800}` | Oxford CS800 cryostream | 28-ID-C | sample | yes |
| Linkam | TemperatureController | `XF:28IDC-ES:2:{LINKAM}` | Linkam thermal stage | 28-ID-C | sample | yes |
| EnvControllers | TemperatureController (?) | `XF:28IDC-ES:1{Env:01}` | Env:01/03/04/06 environment controllers | 28-ID-C | sample | yes |
| SyringePumps | FlowController | `XF:28IDC-ES:1{Pump:Syrng-Ultra:1}` | Ultra syringe pumps 1/2 | 28-ID-C | sample | yes |
| IonChamber | FluxMonitor | `XF:28IDC-BI{IC101}` | ion chamber | 28-ID-C | detection | yes |
| IonMonitor | FluxMonitor | `XF:28IDC-BI{IM:02}` | ion monitor | 28-ID-C | detection | yes |
| QEProSpectrometer | GenericProbe (?) | `XF:28ID2-ES{QEPro:Spec-1}` | Ocean Optics QEPro (optical spectrometer) | 28-ID-2 | detection | yes |
| ResidualGasAnalyzer | GenericProbe (?) | `XF:28IDC-VA{RGA:2}` | residual gas analyzer | 28-ID-C | sample | yes |
| SampleLights | GenericProbe (?) | `XF:28IDC-ES:1{Light:Abs-Hal:1}` | halogen/LED illumination (Light:Abs/Flu) | 28-ID-C | sample | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:28IDA-BI:0{BPM:1-Ax:` | beam position monitors | 28-ID-A | diagnostics | yes |

Device-level prefixes read verbatim from source: the `Mono:DLM-C:1/C:2` double-Laue + `Mono:HRM`, `Mir:VFM`, the `LS335`/`CS:800`/`LINKAM`/`Env` controllers, `Pump:Syrng-Ultra:1/2`, `Det:PE1`, `IC101`/`IM:02` ion chambers.

## Role hints

- **Positioner**: both monos, VFM, slits, filters, pinhole, sample/array/MAD stages, two diffractometers, camera mount + detector stack.
- **Sensor**: two ion chambers, QEPro optical spectrometer, RGA, BPMs.
- **Detector**: Perkin-Elmer flat-panel, scintillation counter.
- **Regulator (dense)**: LS335 cryostat, CS800 cryostream, Linkam, and the Env controllers are all settable-setpoint thermal actuators. With PDF, XPD is the second deep multi-mechanism Regulator deployment in this batch.
- **Flow actuator**: Ultra syringe pumps (FlowController).

## Trust hints

`startup/user_group_permissions.yaml` present; XPD runs `xpdacq` on top of bluesky (same acquisition layer as PDF), the orchestration CORA would replace. XPD is a shipped deployment; aligns with `deployments/xpd/`.

## New-family watch

No new coining. Reinforcements:
- **TemperatureController** (graduated): XPD adds LS335 + CS800 + Linkam + Env, mirroring PDF. The XPD+PDF pair makes the multi-mechanism Regulator deployment a clear, repeated pattern.
- **SyringePumps -> FlowController** (overdue graduation): another consumer (with CHX, and the diamond memo's i22/7-bm/lix/xfp). Strong reinforcement for the recurrence pass.
- **IonChamber/IonMonitor -> FluxMonitor** (graduated): bind directly.
- **Diffractometer (?)** x2, **Pinhole -> Slit (?)**, **QEPro/RGA/Lights/BPM -> GenericProbe (loose)**: confirm at modeling time.

## Deferred / absent

- **DDS pump** (`27-pump_dds.py`) and full **QEPro** detail partly mapped; deferred `FLOW-1`/`OPT-1`.
- The **insertion-device source**: XPD shares the 28-ID straight; no standalone InsertionDevice instantiated in the read modules; carry `SRC-1`.
- Note the multi-hutch PV roots (28-IDA optics, 28-IDC endstation, 28-IDD detector, 28-ID2 spectrometer); confirm the hutch/enclosure mapping with staff.
