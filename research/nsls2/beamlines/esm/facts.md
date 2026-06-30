# Extracted facts: ESM (21-ID)

Candidate device facts for `esm` (NSLS-II 21-ID, electron spectro-microscopy: ARPES + XPEEM/LEEM). Candidates only; confirm every row before modeling. Source: the public **multi-branch** profile collections `NSLS2/esm-arpes-profile-collection` and `NSLS2/esm-xpeem-profile-collection` (`startup/*.py`, read 2026-06; modules `10-machine`, `11-undulator`, `20-motors`, `30-detectors`, `31-ses`, `49/42-ESM_monochromator`, `48-lakeshore`, `46-ESM_LEEM`). Every value is carried `confirm` until ESM staff verify it.

!!! note "Multi-branch: ARPES + XPEEM/LEEM share one source/optics"
    ESM is CORA's first photoemission beamline, modeled as ONE beamline spanning two endstation branches: ARPES (the MBS hemispherical analyzer, `A1Soft`) and XPEEM/LEEM (the `LEEM` electron microscope). They share the EPU source, monochromator, and front-optics mirrors. ESM graduated the Manipulator family. Both branches are folded into this single facts.md.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Branch / Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:21ID-PPS{Sh:FE}` | (PPS shutter) | shared / 21-ID | source | yes |
| PhotonShutter | Shutter | `XF:21IDA-PPS{PSh}` | (PPS shutter) | shared / 21-ID-A | source | yes |
| Mirror1 | Mirror | `XF:21IDA-OP{Mir:1-Ax:` | mirror 1 (+ integrated Slt:4) | shared / 21-ID-A | optics | yes |
| GratingMonochromator | GratingMonochromator | `XF:21IDB-OP{Mono:1` | grating mono (+ slit-defined exit Slt:7/8) | shared / 21-ID-B | optics | yes |
| Mirror3 | Mirror | `XF:21IDB-OP{Mir:3-Ax:` | mirror 3 | shared / 21-ID-B | optics | yes |
| Mirror4A | Mirror | `XF:21IDC-OP{Mir:4A-` | branch-splitting mirror A (ARPES) | shared / 21-ID-C | optics | yes |
| Mirror4B | Mirror | `XF:21IDC-OP{Mir:4B-Ax:` | branch-splitting mirror B (XPEEM) | shared / 21-ID-C | optics | yes |
| MBSAnalyzer | ElectronAnalyzer | `XF:21ID1-ES{A1Soft}` | MBS hemispherical electron analyzer (ARPES) | arpes / 21-ID-1 | detection | yes |
| LEEM | ElectronAnalyzer (?) | `XF:21ID2{LEEM}` | low-energy electron microscope (XPEEM) | xpeem / 21-ID-2 | detection | yes |
| SampleManipulatorLT | Manipulator | `XF:21IDD-ES{LT:1-Manip:EA5_1` | low-temperature sample manipulator (ARPES) | arpes / 21-ID-D | sample | yes |
| SampleManipulatorSP | Manipulator | `XF:21IDD-ES{SP:1-Manip:EA2_1` | sample-prep manipulator | arpes / 21-ID-D | sample | yes |
| TemperatureControllers | TemperatureController | `XF:21ID1-ES{TCtrl:1` | Lakeshore controllers (TCtrl:1/2/3, Chan A/B) | arpes / 21-ID-1 | sample | yes |
| Electrometers | FluxMonitor (?) | `XF:21IDA-BI{EM:1}` | electrometers (EM:1-5) | shared | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:21IDA-BI{EM:BPM01}` | beam position monitor | shared | diagnostics | yes |
| DiagnosticStage | LinearStage | `XF:21IDA-OP{Diag:1` | diagnostic stage | shared / 21-ID-A | diagnostics | yes |
| GateValves | GenericProbe (?) | `XF:21IDA-VA{BC:1-GV:2_D_1}` | vacuum gate valves | shared | vacuum | yes |

Device-level prefixes read verbatim from source: `Mir:1/3/4A/4B`, `Mono:1`, `A1Soft` (MBS analyzer), `LEEM`, the `LT:1`/`SP:1` manipulators, `TCtrl:1-3` Lakeshore.

## Role hints

- **Positioner**: all mirrors (1/3/4A/4B), grating mono, both manipulators, diagnostic stage.
- **Source**: EPU (variable polarization; via 11-undulator.py).
- **Detector / analyzer**: MBS hemispherical analyzer (ARPES), LEEM (XPEEM electron microscope).
- **Regulator**: Lakeshore TCtrl:1-3 (sample temperature).
- **Sensor**: electrometers, BPM.

## Trust hints

`startup/user_group_permissions.yaml` present in each branch; queue-server orchestration. ESM is a shipped deployment that graduated the Manipulator family; aligns with `deployments/esm/`.

## New-family watch

No new coining. Confirmations:
- **MBSAnalyzer -> ElectronAnalyzer** (graduated via ESM + SST): ESM is the origin. Bind directly.
- **LEEM -> ElectronAnalyzer (?)**: a low-energy electron microscope, NOT a hemispherical analyzer; confirm whether it binds ElectronAnalyzer (electron-optical imaging) or warrants a distinct treatment. Single use; do not coin.
- **Manipulator** (graduated via ESM): the LT + SP manipulators are the family's origin. Bind directly.
- **GratingMonochromator** (graduated), **Mirror**, **Lakeshore -> TemperatureController** (graduated): bind directly.

## Deferred / absent

- **EPU undulator**: `11-undulator.py` present in both branches; the concrete EPU PV not isolated to a literal here (`SRC-1`, but it IS an instantiated insertion device, confirm prefix).
- The LEEM internal electron-optical column is an Asset; its lens axes are confirm-pending detail.
- Both branches share the front end; modeled as one beamline per the survey.
