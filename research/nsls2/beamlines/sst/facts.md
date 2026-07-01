# Extracted facts: SST (7-ID)

Candidate device facts for `sst` (NSLS-II 7-ID, soft-and-tender dual-branch, multi-endstation: RSoXS scattering, NEXAFS absorption, HAXPES photoemission). Candidates only; confirm every row before modeling. Source: the public **multi-branch** profile collections `NSLS2/sst-{rsoxs,nexafs,haxpes,vppem}-profile-collection`; the device PVs live in each branch's `startup/device_config.yaml` + `devices.toml` (the Python imports from the `nbs_bl` / `ucal` / `rsoxs` packages). Read 2026-06. Every value is carried `confirm` until SST staff verify it.

!!! note "Dual-branch, multi-endstation; one beamline spanning four configs"
    SST is a soft-and-tender beamline with a shared PGM mono + M1-M4 mirror train feeding four endstation configurations: RSoXS (resonant soft X-ray scattering), NEXAFS (absorption, SR570 drain-current channels), HAXPES (a SES hemispherical analyzer), and VPPEM. All four are folded into this single facts.md; they share `XF:07ID*` optics.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Branch / Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:07ID-PPS{Sh:FE}` | (PPS shutter) | shared / 7-ID | source | yes |
| PhotonShutters | Shutter | `XF:07IDA-PPS{PSh:4}` | photon shutters (PSh:4/7/10) | shared / 7-ID-A | source | yes |
| Mirror1 | Mirror | `XF:07IDA-OP{Mir:M1` | M1 first mirror | shared / 7-ID-A | source | yes |
| GratingMonochromator | GratingMonochromator | `XF:07ID1-OP{Mono:PGM1-Ax:` | PGM plane-grating mono | shared / 7-ID-1 | source | yes |
| Mirror3 | Mirror | `XF:07ID1-OP{Mir:M3ABC` | M3 branch mirror (A/B/C) | shared / 7-ID-1 | source | yes |
| Mirror4 | Mirror | `XF:07ID2-OP{Mir:M4CD` | M4 branch mirror (C/D) | shared / 7-ID-2 | source | yes |
| EndstationSlit11 | Slit | `XF:07ID2-BI{Slt:11-Ax:` | endstation slit | shared / 7-ID-2 | source | yes |
| RSoXSSampleStage | LinearStage | `XF:07ID1-ES:1{Smpl-Ax:` | RSoXS sample stage | rsoxs / 7-ID-1 | sample | yes |
| RSoXSScreens | Screen | `XF:07ID1-ES:1{Scr:1}` | RSoXS screens (Scr:1-5) | rsoxs / 7-ID-1 | source | yes |
| SESAnalyzer | ElectronAnalyzer | `XF:07ID-ES-SES` | SES hemispherical analyzer (HAXPES) | haxpes | detection | yes |
| NEXAFSPreamps | GenericProbe (?) | `XF:07ID-ES{SR570:01}` | SR570 drain-current preamps (NEXAFS, 01-05) | nexafs | detection | yes |
| I400Electrometers | FluxMonitor (?) | `XF:07ID-BI{DM7:I400-1}` | I400 electrometers (DM7, DMR, Slt1) | shared | detection | yes |
| BeamPositionMonitors | GenericProbe (?) | `XF:07ID-BI{BPM:8}` | BPMs (many: 1/4/6/7/8/13/14/16/20/22) | shared | source | yes |
| Diagnostics | LinearStage | `XF:07ID2-BI{Diag:07-Ax:` | diagnostic stages (Diag:07/08) | shared / 7-ID-2 | source | yes |
| BeamlineController | GenericProbe (?) | `XF:07ID1-CT{Bl-Ctrl}` | beamline controller | shared | source | yes |
| GERMDetector | EnergyDispersiveSpectrometer (?) | `XF:07ID1-ES:1{GE:2}` | germanium detector (energy-dispersive) | nexafs/haxpes | detection | yes |

Device-level prefixes read verbatim from source (`device_config.yaml` / `devices.toml`): `Mir:M1/M3ABC/M4CD`, `Mono:PGM1`, `ES-SES` (HAXPES analyzer), the `SR570:01-05` NEXAFS preamps, the `I400` electrometers, `GE:2`.

## Role hints

- **Positioner**: M1/M3/M4 mirrors, PGM mono, RSoXS sample stage, slits, diagnostics.
- **Detector / analyzer**: SES hemispherical analyzer (HAXPES), GE germanium detector, RSoXS area detector (in the `rsoxs` package, templated).
- **Sensor**: SR570 preamps (NEXAFS drain current), I400 electrometers (flux), BPMs.

## Trust hints

`startup/user_group_permissions.yaml` present per branch; SST runs the `nbs_bl` / `ucal` beamline framework on top of bluesky. SST is a shipped deployment (it reuses ElectronAnalyzer); aligns with `deployments/sst/`.

## New-family watch

No new coining. Confirmations:
- **SESAnalyzer -> ElectronAnalyzer** (graduated via ESM + SST): SST is the 2nd consumer that earned the graduation. Bind directly.
- **GratingMonochromator** (graduated): the PGM; bind directly.
- **GERMDetector -> EnergyDispersiveSpectrometer (?)**: a germanium energy-dispersive detector; confirm binding (same WHAT-it-measures discriminator as Xspress3/GeRM at HEX).
- **NEXAFS SR570 preamps / I400 / BPMs -> GenericProbe / FluxMonitor (loose/confirm)**: the drain-current + flux + position cluster; held DIAG-1.

## Deferred / absent

- **RSoXS area detector** + **VPPEM** endstation devices live in the `rsoxs` / `ucal` packages (templated), not isolated to literals here (`DET-1`); the four-branch device set is broader than the config files expose.
- The **insertion-device source** referenced in the configs; concrete EPU prefix not isolated; carry `SRC-1`.
- Multi-branch: all four configs folded into one beamline per the survey; confirm the endstation-to-branch mapping with staff.
