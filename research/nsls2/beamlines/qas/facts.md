# Extracted facts: QAS (7-BM)

Candidate device facts for `qas` (NSLS-II 7-BM, Quick X-ray Absorption Spectroscopy: quick-EXAFS by trajectory energy fly-scan). Candidates only; confirm every row before modeling. Source: the public `NSLS2/qas-profile-collection` (`startup/*.py`, read 2026-06; modules `08-accelerator`, `10-detectors`, `20-motors`, `22-devices`, `29-apb`, `40-xspress3`). Every value is carried `confirm` until QAS staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Quick-EXAFS; the ISS pattern at a bending magnet"
    QAS is the quick-EXAFS sibling of ISS (8-ID): trajectory energy fly-scan with an AnalogPizzaBox (APB) digitizing ion-chamber currents in step, plus fluorescence (Xspress3) and transmission (Keithley/Pilatus). A foil-wheel reference channel and a Linkam sample environment round it out.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:07BM-PPS{Sh:FE}` | (PPS shutter) | 7-BM | source | yes |
| PhotonShutter | Shutter | `XF:07BMA-PPS{Sh:A}` | (PPS shutter) | 7-BM-A | source | yes |
| FluorescenceScreen | Screen | `XF:07BM-BI{FS:1}` | diagnostic screen | 7-BM | diagnostics | yes |
| Monochromator | Monochromator | `XF:07BMA-BI{Mono:1}` | quick-EXAFS scanning mono | 7-BM-A | optics | yes |
| CollimatingMirror | Mirror | `XF:07BM-BI{Mir:Col}` | collimating mirror | 7-BM | optics | yes |
| FocusingMirror | Mirror | `XF:07BMA-OP{Mir:FM` | focusing mirror axes | 7-BM-A | optics | yes |
| WhiteBeamSlit | Slit | `XF:07BMA-OP{Slt:1` | blade axes | 7-BM-A | optics | yes |
| EndstationSlit | Slit | `XF:07BMB-OP{Slt:1` | blade axes | 7-BM-B | optics | yes |
| InclinedBeamPipe | LinearStage | `XF:07BMB-OP{IBP:1-Ax:` | inclined beam-pipe positioning | 7-BM-B | optics | yes |
| FoilWheel | Filter (?) | `XF:07BMB-OP{FoilWheel:1` | reference foil wheels 1/2/3 | 7-BM-B | optics | yes |
| AssemblyStage1 | LinearStage | `XF:07BMB-OP{Asm:1` | detector/sample assembly stage | 7-BM-B | sample | yes |
| AssemblyStage2 | LinearStage | `XF:07BMB-ES{Asm:2` | second assembly stage | 7-BM-B | sample | yes |
| SampleStage | LinearStage | `XF:07BMB-ES{Stg:1` | sample stage | 7-BM-B | sample | yes |
| Linkam | TemperatureController | `XF:07BM-B{Linkam:1}` | Linkam thermal stage (+ LS:01 lakeshore) | 7-BM-B | sample | yes |
| MassFlowController | FlowController (?) | `XF:07BMA-CT{MFC` | gas mass-flow controller | 7-BM-A | sample | yes |
| AnalogPizzaBox | FluxMonitor | `XF:07BMB-CT{PBA:1}` | APB ADC digitizing ion-chamber currents (quick-EXAFS readout) | 7-BM-B | detection | yes |
| KeithleyAmplifiers | GenericProbe (?) | `XF:07BM:K428:A:` | Keithley K428 current amps (A-G) | 7-BM | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:07BMB-ES{Xsp:1}` | Xspress3 SDD | 7-BM-B | detection | yes |
| PilatusDetector | Camera | `XF:07BMB-ES{PIL:3` | Pilatus area detector | 7-BM-B | detection | yes |
| Diagnostic | GenericProbe (?) | `XF:07BMB-BI{Diag:1}` | endstation diagnostic | 7-BM-B | diagnostics | yes |

Device-level prefixes read verbatim from source: `Mono:1`, the `Mir:Col`/`Mir:FM` mirrors, `PBA:1` APB, `K428:A-G` Keithley amps, `Xsp:1`, `FoilWheel:1-3`, the `Linkam:1` + `LS:01` thermal devices, the `MFC` mass-flow controller.

## Role hints

- **Positioner**: mono, both mirrors, slits, IBP, foil wheels, assembly + sample stages.
- **Sensor**: APB (the quick-EXAFS flux digitizer), Keithley amps, diagnostics.
- **Detector**: Xspress3 (fluorescence), Pilatus (transmission/imaging).
- **Regulator**: Linkam + LS:01 lakeshore (thermal); the MFC gas mass-flow controller is a flow actuator.
- **Fly-scan**: the mono trajectory + APB + apb_trigger gate the quick-EXAFS acquisition (the ISS pattern).

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration, the layer CORA would replace.

## New-family watch

No new coining. Reinforcements:
- **AnalogPizzaBox -> FluxMonitor** (graduated): same as ISS; QAS is another consumer.
- **Linkam -> TemperatureController** (graduated, presents Regulator): another consumer.
- **MassFlowController -> FlowController (?)** (graduated): a gas MFC is a flow actuator; bind FlowController, confirm. Adds to the FlowController consumer set.
- **FoilWheel -> Filter (?)**: a reference-foil wheel is an insertable absorber, confirm Filter vs a dedicated reference family (single use here).
- **Keithley/Diag -> GenericProbe (loose)**: held DIAG-1.

## Deferred / absent

- **Mass-flow / gas handling** (`22-devices.py`) partly mapped; deferred `FLOW-1`.
- **Accelerator source** (`08-accelerator.py`) status only; no standalone InsertionDevice (bending magnet); carry `SRC-1`.
