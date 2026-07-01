# Extracted facts: ISS (8-ID)

Candidate device facts for `iss` (NSLS-II 8-ID, inner-shell spectroscopy: EXAFS by trajectory energy fly-scan, plus XES / HERFD on crystal emission spectrometers). Candidates only; confirm every row before modeling. Source: the public `NSLS2/iss-profile-collection` (`startup/*.py`, read 2026-06; modules `08-accelerator`, `10-motors`, `12-hhm`, `20-devices`, `25-sample_environment`, `30-detectors`, `33-apb`, `35-electrometer`, `36-pilatus100k`, `38-xspress3`, `80-johann_spectrometer`, `85-von_hamos_spectrometer`). Every value is carried `confirm` until ISS staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Trajectory fly-scan + two emission spectrometers"
    ISS's signature is energy fly-scanning: the HHM monochromator sweeps a precomputed energy trajectory while the AnalogPizzaBox (APB) digitizes ion-chamber currents in step. The beamline also carries TWO crystal emission spectrometers for XES/HERFD: a Johann (HRS, multi-crystal stack on theta gonios) and a von Hamos (VHS/FIP). Both are modeled below.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:08ID-PPS{Sh:FE}` | (PPS shutter) | 8-ID-A | source | yes |
| PhotonShutter | Shutter | `XF:08IDA-PPS{PSh}` | (PPS shutter) | 8-ID-A | source | yes |
| Monochromator | Monochromator | `XF:08IDA-OP{Mono:HRM` | HHM high-heat-load mono (HRM); energy trajectory fly-scan; bragg + crystal axes (class HHM) | 8-ID-A | source | yes |
| CollimatingMirror | Mirror | `XF:08IDA-OP{Mir:CM` | bender=`-Ax:Bender}W-I`; jacks (Mir:CM) | 8-ID-A | source | yes |
| FocusingMirror | Mirror | `XF:08IDA-OP{Mir:FM` | bender=`-Ax:Bender}W-I`; jacks (Mir:FM) | 8-ID-A | source | yes |
| FilterBox | Filter | `XF:08IDA-OP{Fltr:FB` | filter/attenuator box | 8-ID-A | source | yes |
| KeithleyAmplifiers | GenericProbe (?) | `XF:08ID-ES:{K428}:` | A/B/C/D channels (k1-k4_amp, ICAmplifier_Keithley) | 8-ID-B | detection | yes |
| AnalogPizzaBox | FluxMonitor | `XF:08IDB-CT{PBA:1}:` | APB ADC digitizing ion-chamber currents (apb/apb_ave/apb_stream) | 8-ID-B | detection | yes |
| Pilatus100k_1 | Camera | `XF:08IDB-ES{Det:PIL1}` | Pilatus 100k area detector | 8-ID-B | detection | yes |
| Pilatus100k_2 | Camera | `XF:08IDB-ES{Det:PIL2}` | second Pilatus 100k | 8-ID-B | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:08IDB-ES{Xsp:1}` | Xspress3 SDD fluorescence | 8-ID-B | detection | yes |
| Goniometer | RotaryStage | `XF:08IDB-OP{Gon:Th:1}Mtr` | theta (Gon:Th) | 8-ID-B | sample | yes |
| SampleStage | LinearStage | `XF:08IDB-OP{Stage:Sample` | sample positioning stack | 8-ID-B | sample | yes |
| AuxStage | LinearStage | `XF:08IDB-OP{Stage:Aux1` | x=`-Ax:X}Mtr`; y=`-Ax:Y}Mtr` | 8-ID-B | sample | yes |
| EndstationBPM | GenericProbe (?) | `XF:08IDB-OP{BPM:ES-Ax:` | x=`X}` (endstation beam-position) | 8-ID-B | source | yes |
| DetectorStage | LinearStage | `XF:08IDB-OP{DetStage:2-Ax:` | x/y | 8-ID-B | detection | yes |
| JohannSpectrometer | EmissionSpectrometer (?) | `XF:08IDB-OP{HRS:1-` | analyzer assy=`Ana:Assy:Y}Mtr`; det gonios=`Det:Gon:Theta1/2}Mtr`; crystal stacks=`Stk:1-4:{Roll,Yaw,X,Y}}Mtr` | 8-ID-B | detection | yes |
| VonHamosSpectrometer | EmissionSpectrometer (?) | `XF:08IDB-OP{FIP-VHS:Stage` | stage1/stage2 axes (FIP-VHS); + `Analyzer-Ax:Y/Z` | 8-ID-B | detection | yes |

Device-level prefixes read verbatim from source: `hrm = HRM('XF:08IDA-OP{Mono:HRM'`, `apb = AnalogPizzaBox(prefix="XF:08IDB-CT{PBA:1}:")`, `k1_amp = ICAmplifier_Keithley('XF:08ID-ES:{K428}:A:')`, the HRS Johann stack (`HRS:1-Stk:N:{Roll,Yaw,X,Y}`), and the FIP-VHS von Hamos stages.

## Role hints

- **Positioner**: HHM, both mirrors (with benders), goniometer, sample/aux/detector stages, and every emission-spectrometer axis (Johann crystal stacks + detector gonios, von Hamos stages). Mostly `EpicsMotor`.
- **Sensor**: AnalogPizzaBox (the flux/current digitizer, the fly-scan readout), Keithley amplifiers, endstation BPM.
- **Detector**: Pilatus 100k x2, Xspress3.
- **Controller / fly-scan**: the HHM trajectory manager (`HHMTrajDesc`, `trajectory_manager`) drives the energy trajectory; APB + apb_trigger gate the acquisition. A timing/controller hint, the trajectory is the fly-scan engine.

## Trust hints

`startup/user_group_permissions.yaml` present (queue-server permission model); ISS runs a `user_manager` / `batch-manager` / `scan_manager` stack on top of bluesky. The queue-server is the orchestration layer CORA would replace.

## New-family watch

- **JohannSpectrometer / VonHamosSpectrometer -> EmissionSpectrometer (?)**: `EmissionSpectrometer` IS a catalog Family (loose, used elsewhere). ISS gives it two real consumers in one beamline (Johann + von Hamos). This is a strong **graduation watch**: confirm both bind `EmissionSpectrometer` and whether the two geometries (Johann dispersive-circle vs von Hamos) are one Family or a variant axis. Do NOT coin here; flag for the recurrence pass. Note this relates to the loose `SpectrometerArm` family the survey tracks (n=1 pending a 2nd RIXS): clarify EmissionSpectrometer (XES/HERFD crystal) vs SpectrometerArm (RIXS arm) at graduation.
- **AnalogPizzaBox -> FluxMonitor**: the APB digitizes ion-chamber current = flux. FluxMonitor is graduated; ISS is another consumer. The Keithley amps are the analog front-end (GenericProbe loose).
- **KeithleyAmplifiers / EndstationBPM -> GenericProbe (loose)**: current preamps + beam position; held DIAG-1.

## Deferred / absent

- **Sample environment** (`25-sample_environment.py`) carries cryostat / temperature devices not fully device-mapped in this pass; a possible Regulator/TemperatureController candidate, read before a deployment scaffold (`TEMP-1`).
- **PiCam** (`39-picam.py`), **XIA** (`42-xia.py`) filters, **picoammeter electrometer-new** (`43-electrometer-new.py`) present; not mapped, deferred `DET-1`.
- The **insertion-device source** is referenced via accelerator status (`08-accelerator.py`) but no standalone InsertionDevice device instantiated in the read modules; carry as `SRC-1`.
