# Extracted facts: SMI (12-ID)

Candidate device facts for `smi` (NSLS-II 12-ID, soft matter interfaces: SAXS/WAXS/MAXS with grazing incidence GISAXS/GIWAXS). Candidates only; confirm every row before modeling. Source: the public `NSLS2/smi-profile-collection` (`startup/smibase/*.py`, read 2026-06; modules `base`, `machine`, `energy`, `attenuators`, `crls`, `manipulators`, `beamstop`, `shutter`, `waxschamber`, `linkam`, `electrometers`). The top-level `startup/startup.py` imports from the `smibase` package. Every value is carried `confirm` until SMI staff verify it.

!!! note "Diamond i22 / NSLS-II CMS scattering twin"
    SMI is the GISAXS/GIWAXS soft-matter twin of CMS and Diamond i22. Signature: a DMM mono, CRL transfocator, manipulators (grazing-incidence sample alignment), Linkam thermal stage, and SAXS/WAXS detectors. Devices live in the `smibase` package (instances) imported by startup.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PhotonShutter | Shutter | `XF:12IDA-PPS:2{PSh}` | (PPS shutter) | 12-ID-A | source | yes |
| MultilayerMono | Monochromator | `XF:12IDA{dmm:2}` | double-multilayer mono | 12-ID-A | source | yes |
| Transfocator | Transfocator | `XF:12IDC-OP:2{Lens:CRL-Ax:` | CRL lens stack | 12-ID-C | source | yes |
| HubStage | LinearStage | `XF:12IDC-OP:2{HUB:Stg-Ax:` | hub positioning stage | 12-ID-C | source | yes |
| Filters | Filter | `XF:12IDC-OP:2{Fltr:1-1}` | filter array (Fltr:1-1 .. 1-12) | 12-ID-C | source | yes |
| Manipulator | Manipulator | `XF:12ID2C-ES{MCS:2-Ax:` | grazing-incidence sample manipulator (coordinate system) | 12-ID-C | sample | yes |
| Linkam | TemperatureController | `XF:12ID-ES{LINKAM}` | thermal stage (+ `:{LINKAM}` variant) | 12-ID-C | sample | yes |
| SAXSBeamStop | BeamStop | `XF:12IDC-ES:2{BS:SAXS-Ax:` | SAXS beamstop | 12-ID-C | detection | yes |
| TetrAMM | FluxMonitor | `XF:12ID:2{EM:Tetr1}` | TetrAMM electrometer (I0) | 12-ID | detection | yes |
| BeamPositionMonitor1 | GenericProbe (?) | `XF:12IDA-BI:2{EM:BPM1}` | electrometer BPMs (BPM1/2/3) | 12-ID-A | source | yes |
| SSASlitMonitor | GenericProbe (?) | `XF:12IDB-BI{EM:SSASlit}` | SSA slit current monitor | 12-ID-B | source | yes |

Device-level prefixes read verbatim from `smibase`: `dmm:2`, `Lens:CRL`, `MCS:2` manipulator, the `LINKAM` block, `BS:SAXS`, `EM:Tetr1`, the filter array, the EM BPMs.

## Role hints

- **Positioner**: DMM mono, CRL transfocator, hub stage, filter array, manipulator, beamstop.
- **Sensor**: TetrAMM (I0/flux), EM BPMs, SSA slit monitor.
- **Regulator**: Linkam (thermal setpoint/ramp).
- **Detector**: SAXS/WAXS area detectors (in `waxschamber`; concrete camera roots templated, not isolated).

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. SMI is a shipped deployment with a `smibase`(instances)+`smiclasses`(classes) layout; aligns with `deployments/smi/`.

## New-family watch

No new coining. Confirmations:
- **Transfocator** (graduated): SMI is a CRL consumer (the survey lists smi in the CRL set). Bind directly.
- **Manipulator** (graduated via ESM): SMI's grazing-incidence sample manipulator is another consumer. Bind directly.
- **Linkam -> TemperatureController** (graduated): another consumer. Bind directly.
- **TetrAMM -> FluxMonitor** (graduated): bind directly.
- **EM BPMs / SSA monitor -> GenericProbe (loose)**: held DIAG-1.

## Deferred / absent

- **SAXS/WAXS area-detector** concrete camera PVs are in `waxschamber`/templated, not isolated to a literal here (`DET-1`).
- **Bladecoater / energy / amptek** smibase modules partly mapped; deferred `MISC-1`.
- The **insertion-device source** referenced via `machine`; no standalone InsertionDevice instantiated; carry `SRC-1`.
