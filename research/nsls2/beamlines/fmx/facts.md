# Extracted facts: FMX (17-ID-2)

Candidate device facts for `fmx` (NSLS-II 17-ID-2, frontier microfocusing macromolecular crystallography: rotation MX + serial/fixed-target). Candidates only; confirm every row before modeling. Source: the public `NSLS2/fmx-profile-collection` (`startup/*.py`, read 2026-06; modules `09-machine_00_lsdc`, `10-motors_00_lsdc`, `11-bimorph`, `20-detectors_00_lsdc`, `21-bpm_00_lsdc`, `22-dxp`, `23-attenuator_crl_00_lsdc`, `25-objects`, `26-zebra`, `27-chip_scanner`). Every value is carried `confirm` until FMX staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "MX beamline; reuses the i03 Goniometer family"
    FMX is CORA's 2nd MX after Diamond i03. It is a single-omega rotation goniometer + Eiger with autonomous robot sample exchange and a chip scanner for serial fixed-target. The graduated Goniometer family (from i03) applies. PV namespace is `XF:17ID*:FMX{...}` (FMX shares 17-ID with AMX, the canted MX sibling).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:17ID-PPS:FAMX{Sh:FE}` | (PPS shutter, shared FAMX front end) | 17-ID-A | source | yes |
| PhotonShutter | Shutter | `XF:17IDA-PPS:FMX{PSh}` | (PPS shutter) | 17-ID-A | source | yes |
| FastShutter | Shutter | `XF:17IDC-ES:FMX{Sht:1` | endstation fast shutter | 17-ID-C | source | yes |
| Monochromator | Monochromator | `XF:17IDA-OP:FMX{Mono:DCM` | DCM axes | 17-ID-A | source | yes |
| HorizontalFocusingMirror | Mirror | `XF:17IDA-OP:FMX{Mir:HFM-PS}` | HFM bimorph (piezo segments) | 17-ID-A | source | yes |
| WhiteBeamSlit | Slit | `XF:17IDA-OP:FMX{Slt:1` | blade axes | 17-ID-A | source | yes |
| CRLAttenuator | Filter | `XF:17IDC-OP:FMX{Attn:BCU` | BCU attenuator (CRL/transmission LUT) | 17-ID-C | source | yes |
| Collimator | Collimator | `XF:17IDC-ES:FMX{Colli:1` | beam-defining collimator | 17-ID-C | source | yes |
| Goniometer | Goniometer | `XF:17IDC-ES:FMX{Gon:1` | single-omega gonio (+ `Gon:1-Sht` shutter, `Gon:1-Vec` vector) | 17-ID-C | sample | yes |
| GoniometerStage2 | LinearStage | `XF:17IDC-ES:FMX{Gon:2-Ax:` | secondary gonio stage | 17-ID-C | sample | yes |
| ChipScanner | LinearStage | `XF:17IDC-ES:FMX{Chip:1-Ax:` | fixed-target serial chip raster | 17-ID-C | sample | yes |
| DropStage | LinearStage | `XF:17IDC-ES:FMX{Drp:1-Ax:` | drop/sample-delivery stage | 17-ID-C | sample | yes |
| SampleMicroscope | GenericProbe (?) | `XF:17IDC-ES:FMX{Mic:1` | on-axis sample microscope | 17-ID-C | sample | yes |
| SampleLight | GenericProbe (?) | `XF:17IDC-ES:FMX{Light:1` | sample illumination | 17-ID-C | sample | yes |
| Eiger16M | Camera | `XF:17IDC-ES:FMX{Det:Eig16M}` | Eiger 16M (rotation MX) | 17-ID-C | detection | yes |
| MerlinDetector | Camera | `XF:17IDC-ES:FMX{Det:Mer}` | Merlin (serial/fast) | 17-ID-C | detection | yes |
| BeamStop | BeamStop | `XF:17IDC-ES:FMX{BS:1` | beamstop axes | 17-ID-C | detection | yes |
| DXPController | GenericProbe (?) | `XF:17IDC-BI:FMX{Keith:1}` | Keithley / DXP front-end | 17-ID-C | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:17IDA-BI:FMX{BPM:1` | BPMs (BPM:1-4) | 17-ID-A | source | yes |
| BestMonitor | GenericProbe (?) | `XF:17IDC-BI:FMX{Best:2}` | BEST beam-stabilization monitor | 17-ID-C | source | yes |
| Zebra1 | TimingController (?) | `XF:17IDA-ES:FMX{Zeb:1}` | Zebra gating (Zeb:1-3) | 17-ID-A | detection | yes |
| MotionControllerSender | MotionController (?) | `XF:17ID-CT:FMX{MC17:Sender}` | MC17 motion-controller coordinator | 17-ID | sample | yes |

Device-level prefixes read verbatim from source: `Mono:DCM`, `Mir:HFM-PS` (bimorph), `Gon:1` goniometer with shutter/vector sub-devices, `Attn:BCU` CRL attenuator, `Chip:1` serial scanner, `Det:Eig16M`/`Det:Mer`, the Zebra trio.

## Role hints

- **Positioner**: mono, HFM bimorph, slit, collimator, goniometer + secondary stage, chip scanner, drop stage, beamstop.
- **Sensor**: BPMs, BEST monitor, Keithley/DXP.
- **Detector**: Eiger 16M (rotation), Merlin (serial).
- **Timing**: three Zebras gate data collection.
- **Sample handling**: the robot sample exchange is the LSDC (macromolecular data collection) control; modeled as a Positioner + Clearance + Subject custody thread, NOT a SampleChanger Family (the i03/19-BM/32-ID pattern).

## Trust hints

`startup/user_group_permissions.yaml` present; FMX runs LSDC (the NSLS-II MX beamline control) on top of bluesky. The LSDC orchestration is the layer CORA's edge would conduct over / replace. Aligns with `deployments/fmx/`.

## New-family watch

No new coining. Confirmations:
- **Goniometer** (graduated via i03): FMX is the 2nd MX consumer; bind directly. Single-omega here vs i03's six-axis Smargon, a variant within the family.
- **Collimator** (catalog Family): bind directly.
- **CRLAttenuator -> Filter (?)**: the BCU attenuator combines CRL transmission + attenuation; confirm Filter vs Transfocator binding (it is an attenuation device here, not focusing).
- **Eiger 16M + Merlin -> Camera**: bind directly.
- **Zebra -> TimingController (?)**, **BPM/BEST/Keith -> GenericProbe (loose)**: fleet-wide patterns, confirm.

## Deferred / absent

- **AMX sibling**: the source carries `XF:17IDA-OP:AMX{Mono:DCM}` (the canted AMX branch shares the 17-ID front end). AMX is its own beamline (Batch C); not modeled here.
- **powerbrick** (`24-powerbrick.py`) motion controller detail and **bimorph** segment-level axes partly mapped; deferred `MISC-1`.
- The **insertion-device source** referenced via `09-machine`; no standalone InsertionDevice instantiated; carry `SRC-1`.
