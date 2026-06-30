# Extracted facts: XFP (17-BM)

Candidate device facts for `xfp` (NSLS-II 17-BM, X-ray footprinting: white/pink-beam radiolytic dose delivery to solution biomolecules, structural readout offline by mass spec). Candidates only; confirm every row before modeling. Source: the public `NSLS2/xfp-profile-collection` (`startup/*.py`, read 2026-06; modules `10-fp-devs`, `10-motors-bl`, `10-motors-fe`, `11-shutters`, `14-diode`, `15-electrometer`, `20-bpm`, `25-filter`). Every value is carried `confirm` until XFP staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Dose-delivery beamline; no area/imaging detector"
    XFP is a dose-delivery beamline: the run produces a footprinted SAMPLE plus a dose record (exposure x flux x attenuation), not a diffraction/imaging dataset. The structural readout is OFFLINE mass spec (a seam, not a device). The dose chain is filters + a timed shutter + flux monitors + sample/flow delivery. There is no scattering or area detector.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:17BM-PPS{Sh:FE}` | (PPS shutter) | 17-BM | source | yes |
| EPSShutter | Shutter | `XF:17BMA-EPS{Sh:1}` | EPS-controlled shutter (dose timing) | 17-BM-A | source | yes |
| Monochromator | Monochromator | `XF:17BMA-OP{Mono:1-Ax:` | mono axes (mono mode; white/pink for dose) | 17-BM-A | optics | yes |
| Mirror1 | Mirror | `XF:17BM-OP{Mir:1` | mirror axes | 17-BM | optics | yes |
| ADCSlit | Slit | `XF:17BMA-OP{Slt:ADC-Ax:` | ADC slit | 17-BM-A | optics | yes |
| PinkBeamSlit | Slit | `XF:17BMA-OP{Slt:PB-Ax:` | pink-beam slit | 17-BM-A | optics | yes |
| FilterStage | Filter | `XF:17BMA-ES:1{Fltr:1-Ax:` | Al filter wheel (dose-rate attenuation) | 17-BM-A | optics | yes |
| OpticsStage2 | LinearStage | `XF:17BMA-OP{Stg:2-Ax:` | optics stage | 17-BM-A | optics | yes |
| BeamPositionMonitorOptics | GenericProbe (?) | `XF:17BMA-OP{Bpm:1-Ax:` | optics BPM | 17-BM-A | diagnostics | yes |
| SampleStage | LinearStage | `XF:17BMA-ES:1{Sam:1-Ax:` | sample positioning | 17-BM-A | sample | yes |
| SampleTable1 | Table | `XF:17BMA-ES:1{Tbl:1-Ax:` | sample table (+ Tbl:3) | 17-BM-A | sample | yes |
| CVDStage | LinearStage | `XF:17BMA-ES:1{CVD:1-Ax:` | CVD diamond / window stage | 17-BM-A | sample | yes |
| SyringePump1 | FlowController | `XF:17BM-ES:1{Pmp:01}` | sample-delivery syringe pump (+ Pmp:02) | 17-BM | sample | yes |
| FractionCollector | GenericProbe (?) | `XF:17BM-ES:1{FC:1}` | fraction collector | 17-BM | sample | yes |
| HighThroughputFly | LinearStage | `XF:17BMA-ES:2{HTFly:1-Ax:` | high-throughput fly stage | 17-BM-A | sample | yes |
| SampleModules | LinearStage | `XF:17BMA-ES:2{Mod:12-Ax:` | sample modules (Mod:12, Mod:34) | 17-BM-A | sample | yes |
| Stage7 | LinearStage | `XF:17BMA-ES:2{Stg:7-Ax:` | endstation stage (+ Stg:5, Stg:9) | 17-BM-A | sample | yes |
| DelayGenerator | TimingController | `XF:17BMA-ES:2{DG:1}` | delay generator (shutter timing = dose) | 17-BM-A | detection | yes |
| TimingControlModule | TimingController (?) | `XF:17BMA-ES:2{TCM:1}` | timing control module | 17-BM-A | detection | yes |
| IonChamber1 | FluxMonitor | `XF:17BM-BI{EM:1}` | ion chamber / electrometer (+ EM:2; flux for dose) | 17-BM | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:17BM-BI{EM:BPM1}` | electrometer BPM | 17-BM | diagnostics | yes |
| PinkBeamGuard | GenericProbe (?) | `XF:17BM-ES{PBG:1}` | pink-beam guard | 17-BM | source | yes |
| DiodeLocal | GenericProbe (?) | `XF:17BMA-CT{DIODE-Local:` | local diode (+ DIODE-PDM:1) | 17-BM-A | detection | yes |

Device-level prefixes read verbatim from source: `Mono:1`, `Mir:1`, `Slt:ADC`/`Slt:PB`, `Fltr:1` Al wheel, `Pmp:01`/`Pmp:02` syringe pumps, `DG:1` delay generator, `EM:1`/`EM:2` flux monitors, `FC:1` fraction collector.

## Role hints

- **Positioner**: mono, mirror, slits, filter wheel, all sample/module/fly stages, tables.
- **Sensor**: ion chambers / electrometers (flux, the dose input), BPMs, diodes.
- **Flow actuator**: syringe pumps (sample delivery).
- **Timing (dose-defining)**: the delay generator + EPS shutter set the exposure time, which IS the dose. This is the beamline's defining control.
- **No area/scattering detector** (the headline): structural readout is offline mass spec.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. Aligns with `deployments/xfp/`. The dose record (exposure x flux x attenuation) is the data-of-record CORA owns; the MS is the offline-readout seam.

## New-family watch

No new coining. Notes:
- **SyringePump -> FlowController** (graduated): XFP is a further consumer (with chx/xpd here, and the Diamond memo's i22/7-bm/lix). Strong cross-facility reinforcement; bind directly.
- **DelayGenerator / TCM -> TimingController** (graduated): the dose-timing chain; bind directly (this is the canonical TimingController-as-dose-clock use).
- **IonChamber -> FluxMonitor** (graduated): bind directly; here flux is the dose input.
- **FractionCollector / PinkBeamGuard / Diode / BPM -> GenericProbe (loose)**: confirm; the fraction collector + 96-well plate are custody/seam, not devices.

## Deferred / absent

- **NO detector family** by design (footprinting has no area/diffraction detector); the offline mass spec is a readout seam (`READOUT-1`), not modeled as a device.
- The bending-magnet **source** referenced via `10-motors-fe.py`; no standalone InsertionDevice (bending magnet); carry `SRC-1`.
