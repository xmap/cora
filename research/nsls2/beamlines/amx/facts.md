# Extracted facts: AMX (17-ID-1)

Candidate device facts for `amx` (NSLS-II 17-ID-1, automated macromolecular crystallography: rotation MX with high-throughput robot exchange). Candidates only; confirm every row before modeling. Source: the public `NSLS2/amx-profile-collection` (`startup/*.py`, read 2026-06; modules `09-machine`, `10-motors`, `20-detectors`, `21-bpm`, `22-dxp`, `25-zebra`, `26-robot`, `28-governor`). Every value is carried `confirm` until AMX staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "MX sibling of FMX on the canted 17-ID straight"
    AMX shares the 17-ID straight with FMX (PV namespace `XF:17ID*:AMX{...}`). It is a rotation-MX goniometer + Merlin/Eiger with robot sample exchange and a governor (state machine) coordinating mount/center/collect. Reuses the graduated Goniometer family (i03/FMX).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PhotonShutter | Shutter | `XF:17IDA-OP:AMX{Slt:0` | (and front-end shutter shared FAMX) | 17-ID-A | source | yes |
| FastShutter | Shutter | `XF:17IDB-ES:AMX{Sht:1` | endstation fast shutter | 17-ID-B | source | yes |
| Monochromator | Monochromator | `XF:17IDA-OP:AMX{Mono:DCM` | DCM axes (+ dflux, CorrectDCM feedback) | 17-ID-A | optics | yes |
| ToroidalDeflectingMirror | Mirror | `XF:17IDA-OP:AMX{Mir:TDM` | TDM axes | 17-ID-A | optics | yes |
| WhiteBeamSlit0 | Slit | `XF:17IDA-OP:AMX{Slt:0` | blade axes | 17-ID-A | optics | yes |
| WhiteBeamSlit1 | Slit | `XF:17IDA-OP:AMX{Slt:1` | blade axes | 17-ID-A | optics | yes |
| CRLAttenuator | Filter | `XF:17IDB-OP:AMX{Attn:BCU` | BCU attenuator (transmission LUT) | 17-ID-B | optics | yes |
| KBMirror | Mirror | `XF:17IDB-ES:AMX{Mir:1` | KB refocus mirror | 17-ID-B | optics | yes |
| Collimator | Collimator | `XF:17IDB-ES:AMX{Colli:1` | beam-defining collimator | 17-ID-B | optics | yes |
| Goniometer | Goniometer | `XF:17IDB-ES:AMX{Gon:1` | single-omega goniometer | 17-ID-B | sample | yes |
| SampleMicroscope | GenericProbe (?) | `XF:17IDB-ES:AMX{Mic:1` | on-axis sample microscope | 17-ID-B | sample | yes |
| MerlinDetector | Camera | `XF:17IDB-ES:AMX{Det:Mer}` | Merlin detector | 17-ID-B | detection | yes |
| BeamStop | BeamStop | `XF:17IDB-ES:AMX{BS:1` | beamstop axes | 17-ID-B | detection | yes |
| EMBLDetector | GenericProbe (?) | `XF:17IDB-ES:AMX{EMBL}` | EMBL beam-conditioning / detection unit | 17-ID-B | detection | yes |
| DXPController | GenericProbe (?) | `XF:17IDB-BI:AMX{Keith:1}` | Keithley/DXP front-end | 17-ID-B | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:17IDA-BI:AMX{BPM:1` | BPMs (BPM:1-3) | 17-ID-A | diagnostics | yes |
| Zebra1 | TimingController (?) | `XF:17IDB-ES:AMX{Zeb:1}` | Zebra gating (Zeb:1-2) | 17-ID-B | detection | yes |
| BestMonitor | GenericProbe (?) | `XF:16IDB-CT{Best}` | BEST beam-stabilization monitor (shared) | 16-ID | diagnostics | yes |

Device-level prefixes read verbatim from source: `Mono:DCM` (+ `CorrectDCM` feedback), `Mir:TDM`, `Attn:BCU`, `Gon:1` goniometer, `Colli:1`, `Det:Mer`, the Zebra pair. Robot is `26-robot.py` (sample exchange).

## Role hints

- **Positioner**: mono, TDM + KB mirrors, slits, collimator, goniometer, beamstop.
- **Sensor**: BPMs, Keithley/DXP, BEST monitor.
- **Detector**: Merlin (+ Eiger via shared FAMX detector pool).
- **Timing**: Zebra pair.
- **Sample handling**: robot exchange + governor state machine = Positioner + Clearance + Subject custody (the MX pattern), NOT a SampleChanger Family.

## Trust hints

`startup/user_group_permissions.yaml` present; AMX runs LSDC (NSLS-II MX control) + a governor state machine on top of bluesky. The governor (mount/center/collect coordination) is orchestration CORA's edge would conduct over. Aligns with `deployments/amx/`.

## New-family watch

No new coining. Confirmations:
- **Goniometer** (graduated via i03): AMX is a further MX consumer (with FMX). Bind directly.
- **Collimator** (catalog): bind directly.
- **CRLAttenuator -> Filter (?)**: BCU attenuator (same as FMX); confirm Filter vs Transfocator (attenuation here).
- **EMBL / Zebra / BPM / Keith / BEST -> GenericProbe / TimingController (loose/confirm)**: fleet-wide patterns.

## Deferred / absent

- **Robot** (`26-robot.py`) custody thread and **governor** (`28-governor.py`) state machine are orchestration, captured as notes not devices.
- **powerbrick** motion-controller detail deferred `MISC-1`.
- Shares the 17-ID front end with FMX (`FAMX` shutter); no standalone InsertionDevice; carry `SRC-1`.
