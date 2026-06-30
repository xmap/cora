# Extracted facts: XFM (4-BM)

Candidate device facts for `xfm` (NSLS-II 4-BM, X-ray fluorescence microprobe: raster XRF mapping on a bending magnet). Candidates only; confirm every row before modeling. Source: the public `NSLS2/xfm-profile-collection` (`startup/*.py`, read 2026-06; modules `10-stages`, `20-scaler`, `30-xspress3`). The public profile collection is THIN. Every value is carried `confirm` until XFM staff verify it.

!!! note "Thin public source; CORA's 2nd scanning-XRF after 2-ID"
    The public XFM profile collection exposes only the sample scanning stages, a scaler, and the Xspress3 fluorescence detector at the top level. The mono, mirrors, and source are not in the read modules. XFM is a shipped deployment; this pass records what public source supports.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| SampleScanStage | LinearStage | `XF:04BMC-ES:2` | raster XRF sample stages (x/y) | 4-BM-C | sample | yes |
| ScalerCounter | GenericProbe (?) | `XF:04BM-ES:2{Sclr:1}` | scaler channels | 4-BM | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:04BMC-ES{x3m:1}` | Xspress3 mini (x3m) SDD fluorescence | 4-BM-C | detection | yes |

Device-level prefixes read verbatim from source: `XF:04BMC-ES:2` stages, `Sclr:1`, `x3m:1` (Xspress3 mini). Only these appear in the public top-level modules.

## Role hints

- **Positioner**: sample scanning stages (the XRF raster).
- **Sensor**: scaler.
- **Detector**: Xspress3 mini (energy-dispersive fluorescence).

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. XFM is a shipped deployment; aligns with `deployments/xfm/`. The survey notes XFM uses Xspress3 + Maia detectors; only Xspress3 appears in public source here.

## New-family watch

- **FluorescenceSpectrometer -> EnergyDispersiveSpectrometer** (graduated): the Xspress3 mini; bind directly.
- **SampleScanStage -> LinearStage** (graduated): bind directly.

## Deferred / absent

- **Mono, mirrors, bending-magnet source, the Maia detector**: ABSENT from the public top-level modules. Not invented; the shipped `deployments/xfm/` carries the fuller model (`COVERAGE-1`).
