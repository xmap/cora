# Extracted facts: ISR (4-ID)

Candidate device facts for `isr` (NSLS-II 4-ID, in-situ and resonant hard X-ray scattering). Candidates only; confirm every row before modeling. Source: the public `NSLS2/isr-profile-collection` (`startup/*.py`, read 2026-06; modules `02-mirrors`, `03-bpm`, `04-dcm`, `10-optics`, `15-attenuators`, `20-area-detectors`). Every value is carried `confirm` until ISR staff verify it.

!!! note "Commissioning-phase / optics-first scaffold"
    The public ISR profile collection is an early/optics-first scaffold: the mono + mirrors + an Eiger 1M and a th/zeta diffractometer stub (`Dif:ISD`) are present; the full multi-circle diffractometer, in-situ environment, and resonant/polarization analysis are absent from source (deferred, not invented). This matches CORA's deliberately-partial ISR deployment.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| Monochromator | Monochromator | `XF:04IDA-OP:1{Mono:DCM` | DCM axes | 4-ID-A | source | yes |
| HorizontalFocusingMirror | Mirror | `XF:04IDA-OP:1{Mir:HFM` | HFM | 4-ID-A | source | yes |
| VerticalFocusingMirror | Mirror | `XF:04IDA-OP:1{Mir:VFM` | VFM | 4-ID-A | source | yes |
| DoubleHighResMirror | Mirror | `XF:04IDB-OP:1{Mir:DHRM` | DHRM | 4-ID-B | source | yes |
| Diffractometer | Diffractometer (?) | `XF:04IDD-ES:1{Dif:ISD-Ax:` | th + zeta only (partial diffractometer stub) | 4-ID-D | sample | yes |
| Eiger1M | Camera | `XF:04IDD-ES{Det:Eig1M}` | Eiger 1M area detector | 4-ID-D | detection | yes |
| BeamPositionMonitor3 | GenericProbe (?) | `XF:04IDB-BI:1{BPM:3-` | BPM | 4-ID-B | source | yes |

Device-level prefixes read verbatim from source: `Mono:DCM`, `Mir:HFM/VFM/DHRM`, `Dif:ISD` (th/zeta), `Det:Eig1M`.

## Role hints

- **Positioner**: DCM, three mirrors, the partial diffractometer (th/zeta).
- **Detector**: Eiger 1M.
- **Sensor**: BPM.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. ISR is a shipped deployment, deliberately partial; aligns with `deployments/isr/`.

## New-family watch

- **Diffractometer (?)**: `Dif:ISD` exposes only th + zeta here, a partial stub, not a full multi-circle diffractometer. Adds to the loose Diffractometer recurrence watch but with the weakest contract (2 axes). Confirm whether it graduates to a real diffractometer when more axes are wired.
- **Monochromator / Mirror / Camera**: bind to graduated families directly.

## Deferred / absent

- **The multi-circle diffractometer** (beyond th/zeta), **in-situ environment**, **resonant energy axis**, and **polarization analysis** are ABSENT from public source -> deferred (DIFF-1 / INSITU-1 / RESONANT-1), not invented. This matches the deployment's partial scaffold.
- **Attenuators** (`15-attenuators.py`) present but not isolated to a literal prefix here; deferred `ATTN-1`.
- The **insertion-device source**: no standalone InsertionDevice instantiated; carry `SRC-1`.
