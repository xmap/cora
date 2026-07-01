# Extracted facts: SIX (2-ID)

Candidate device facts for `six` (NSLS-II 2-ID, soft X-ray resonant inelastic scattering: RIXS). Candidates only; confirm every row before modeling. Source: the public `NSLS2/six-profile-collection` (`startup/*.py`, read 2026-06; modules `04-epu`, `10-mirror`, `12-slits`, `13-chamber`, `20-diagon`, `21-areadetector`, `22-rixscam`, `23-detectors`, `24-sample_envs`, `25-temp_control`). Every value is carried `confirm` until SIX staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Soft X-ray RIXS; the long spectrometer arm"
    SIX is CORA's first soft X-ray beamline (already deployed). Its signature is the RIXS spectrometer: a long arm carrying mirrors 5/6 and the RIXSCam detector, fed by an EPU + grating mono. The loose SpectrometerArm family (n=1, pending a 2nd RIXS) originates here.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| InsertionDevice | InsertionDevice | `XF:02ID-ID{EPU:1}` | EPU variable-polarization undulator (+ EPU:1-FLT) | 2-ID | source | yes |
| Mirror1 | Mirror | `XF:02IDA-OP{Mir:1-Ax:` | mirror 1 (+ integrated Slt:4) | 2-ID-A | source | yes |
| GratingMonochromator | GratingMonochromator | `XF:02IDB-OP{Mono:1-Slt:8_U_1` | grating mono (Mono:1, with slit-defined exit) | 2-ID-B | source | yes |
| Mirror3 | Mirror | `XF:02IDC-OP{Mir:3-Ax:` | mirror 3 (+ Slt:12) | 2-ID-C | source | yes |
| Mirror4 | Mirror | `XF:02IDC-OP{Mir:4-Ax:` | mirror 4 (+ Slt:18) | 2-ID-C | source | yes |
| ExitSlit | Slit | `XF:02IDC-OP{Slt:1-Ax:` | exit slit | 2-ID-C | source | yes |
| SpectrometerMirror5 | SpectrometerArm (?) | `XF:02IDD-ES{Mir:5-Ax:` | RIXS arm mirror 5 | 2-ID-D | detection | yes |
| SpectrometerMirror6 | SpectrometerArm (?) | `XF:02IDD-ES{Mir:6-Ax:` | RIXS arm mirror 6 | 2-ID-D | detection | yes |
| SampleChamberSlit | Slit | `XF:02IDD-ES{DC:1-Slt:1` | sample/detector chamber slit | 2-ID-D | sample | yes |
| RIXSCam | Camera | `XF:02ID1-ES{RIXSCam}` | RIXS CCD detector | 2-ID-D | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:02ID1-ES:1{Sclr:1}` | scaler channels | 2-ID-D | detection | yes |
| Nanovoltmeter | GenericProbe (?) | `XF:02ID1-ES{Nanovmeter:1}` | nanovoltmeter | 2-ID-D | detection | yes |
| Electrometers | FluxMonitor (?) | `XF:02IDA-BI{EM:1}` | electrometers EM:1-10 across hutches | 2-ID-A | detection | yes |
| DiagnosticStage | LinearStage | `XF:02IDA-OP{Diag:1-Ax:` | diagnostic stage | 2-ID-A | source | yes |
| SampleEnvironment | TemperatureController (?) | `XF:02ID1-ES{GPIO:1_` | sample-environment / temp control (24/25 modules) | 2-ID-D | sample | yes |

Device-level prefixes read verbatim from source: `EPU:1`, `Mir:1/3/4/5/6`, `Mono:1`, the `RIXSCam`, the EM electrometer bank, the Diagon diagnostic.

## Role hints

- **Positioner**: all mirrors (1/3/4 optics, 5/6 spectrometer arm), grating mono, slits, diagnostic stage.
- **Source**: EPU (variable polarization).
- **Sensor**: electrometer bank (EM:1-10), scaler, nanovoltmeter.
- **Detector**: RIXSCam (the RIXS CCD).

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. SIX is a shipped deployment; aligns with `deployments/six/`.

## New-family watch

- **SpectrometerArm (LOOSE, n=1)**: mirrors 5/6 on the RIXS arm. This is the origin of the loose SpectrometerArm family the survey tracks; it stays loose pending a 2nd RIXS (a true rule-of-three). Do NOT graduate from SIX alone. Distinct from EmissionSpectrometer (ISS Johann/von Hamos crystal): SpectrometerArm = grazing-incidence RIXS arm, EmissionSpectrometer = crystal XES/HERFD. Clarify both at graduation.
- **GratingMonochromator** (graduated via CSX): SIX is another soft X-ray consumer; bind directly.
- **InsertionDevice (EPU)** (catalog): bind directly.
- **Electrometers -> FluxMonitor (?)**, **SampleEnvironment -> TemperatureController (?)**: confirm role (settable vs read).

## Deferred / absent

- **Sample environments** (`24-sample_envs.py`) + **temp control** (`25`) + **chiller** (`26`) partly mapped; if a settable thermal controller, another TemperatureController consumer (`TEMP-1`).
- **Diagon** (`20-diagon.py`) diagnostic and **mask** (`14`) deferred `DIAG-2`.
- Insertion device is the EPU (modeled); no separate question.
