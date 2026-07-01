# Extracted facts: NYX (19-ID)

Candidate device facts for `nyx` (NSLS-II 19-ID, macromolecular crystallography). Candidates only; confirm every row before modeling. Source: the public `NSLS2/nyx-profile-collection` (`startup/*.py`, read 2026-06; modules `00-base`, `.10-motors`, `.20-detectors`, `25-zebra`, `50-objects`). Every value is carried `confirm` until NYX staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "MX beamline; reuses the i03 Goniometer family"
    NYX is an MX beamline (rotation crystallography) with a single goniometer, robot sample exchange, Eiger-class detector, and hi/lo-magnification on-axis viewing. The graduated Goniometer family (i03) applies; CORA's 3rd-plus MX after i03 / FMX / AMX.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| Monochromator | Monochromator | `XF:19IDC-OP{Mono:DCM` | DCM axes | 19-ID-C | source | yes |
| Mirror1 | Mirror | `XF:19IDC-OP{Mir:1` | mirror axes | 19-ID-C | source | yes |
| WhiteBeamSlit | Slit | `XF:19IDC-OP{Slt:WB` | blade axes | 19-ID-C | source | yes |
| MonoBeamSlit | Slit | `XF:19IDC-OP{Slt:MB` | blade axes | 19-ID-C | source | yes |
| BeamMonitor | GenericProbe (?) | `XF:19IDC-OP{BM:1` | beam monitor | 19-ID-C | source | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:19IDC-OP{BPM:1` | BPM 1/2/3 | 19-ID-C | source | yes |
| Goniometer | Goniometer | `XF:19IDC-ES{Gon:1` | single-axis gonio (+ `Gon:1-Vec` vector) | 19-ID-C | sample | yes |
| Robot | Positioner | `XF:19IDC-ES{Rbt:1}` | sample-exchange robot | 19-ID-C | sample | yes |
| Collimator | Collimator (?) | `XF:19IDC-ES{Gbl:1` | beam-defining collimator / guard | 19-ID-C | source | yes |
| BeamShaping | LinearStage (?) | `XF:19IDC-ES{Opt:1` | endstation optic stage | 19-ID-C | source | yes |
| BeamStop | BeamStop | `XF:19IDC-ES{BS:1` | beamstop axes | 19-ID-C | detection | yes |
| Backlight | GenericProbe (?) | `XF:19IDC-ES{BP:1` | backlight/pin | 19-ID-C | sample | yes |
| DetectorStage | LinearStage | `XF:19IDC-ES{Det:1` | detector positioning | 19-ID-C | detection | yes |
| DetectorTable | Table | `XF:19IDC-ES{Tbl:1` | detector table | 19-ID-C | detection | yes |
| HighMagCamera | Camera | `XF:19IDC-ES{Cam:HiMag` | high-magnification on-axis view | 19-ID-C | sample | yes |
| LowMagCamera | Camera | `XF:19IDC-ES{Cam:LoMag` | low-magnification on-axis view | 19-ID-C | sample | yes |
| BeamDefiningSlit | Slit | `XF:19IDC-ES{Slt:BD` | beam-defining slit | 19-ID-C | source | yes |
| Zebra | TimingController (?) | `XF:19IDC-ES{Zeb:1}` | data-collection gating | 19-ID-C | detection | yes |
| KeithleyAmplifier | GenericProbe (?) | `XF:19ID1-BI:NYX{Keith:1}` | Keithley current amp | 19-ID | detection | yes |
| VacuumGauges | GenericProbe (?) | `XF:19IDD-CT{Ion:1-Gauge:1}` | ion-gauge vacuum (Ion:1/2) | 19-ID-D | vacuum | yes |

Device-level prefixes read verbatim from source: `Mono:DCM`, `Mir:1`, `Gon:1` (+ `Gon:1-Vec`), `Rbt:1` robot, `Det:1`/`Tbl:1`, the HiMag/LoMag cameras, `Zeb:1`.

## Role hints

- **Positioner**: mono, mirror, slits, goniometer, robot, collimator, optic stage, detector stage/table, beamstop.
- **Sensor**: beam monitor, BPMs, Keithley, vacuum gauges.
- **Detector**: the `Det:1` area detector (Eiger-class for MX), hi/lo-mag viewing cameras.
- **Timing**: Zebra gates rotation data collection.
- **Sample handling**: the robot (`Rbt:1`) folds to Positioner + Clearance + Subject custody, NOT a SampleChanger Family (the i03/FMX pattern).

## Trust hints

`startup/user_group_permissions.yaml` present; NYX MX data collection runs on top of bluesky, the orchestration CORA's edge would conduct over.

## New-family watch

No new coining. Confirmations:
- **Goniometer** (graduated via i03): NYX is a further MX consumer; bind directly. Single-axis here.
- **Collimator (?)**: confirm `Gbl:1` is the catalog Collimator vs a guard slit.
- **Camera** (hi/lo-mag), **BeamStop**, **Table**: bind directly.
- **Zebra -> TimingController (?)**, **BM/BPM/Keith/Backlight/gauges -> GenericProbe (loose)**: fleet-wide patterns.

## Deferred / absent

- **custom_plans** (`95-custom_plans.py`) is acquisition logic, not devices.
- The **insertion-device source** at 19-ID; status only in `00-base.py`; carry `SRC-1`.
- NYX is a newer beamline; the profile-collection is comparatively thin, so the device set may grow (`COVERAGE-1`); every row here is read from source, none inferred.
