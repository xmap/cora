# Extracted facts: IXS (10-ID)

Candidate device facts for `ixs` (NSLS-II 10-ID, momentum-resolved hard inelastic X-ray scattering). Candidates only; confirm every row before modeling. Source: the public `NSLS2/ixs-profile-collection` (`startup/*.py`, read 2026-06; modules `10-machine`, `10-optics`, `25-pseudomotors`, `26-cameras`). Every value is carried `confirm` until IXS staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Hard IXS; the analyzer + spectrometer arm"
    IXS is CORA's first hard inelastic scattering beamline. Its signature is the analyzer/spectrometer in the 10-ID-D hutch (`Analy:1`, `Spec:1`, `MCM:1` multi-crystal monochromator) fed by a DCM + HRM2 high-resolution mono chain.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| Monochromator | Monochromator | `XF:10IDA-OP{Mono:DCM` | DCM axes | 10-ID-A | source | yes |
| HighResMono2 | Monochromator | `XF:10IDB-OP{Mono:HRM2` | high-resolution mono | 10-ID-B | source | yes |
| WhiteBeamSlit | Slit | `XF:10IDA-OP{Slt:1` | blade axes | 10-ID-A | source | yes |
| SecondarySourceAperture | Slit | `XF:10IDB-OP{SSA:1` | SSA blades | 10-ID-B | source | yes |
| HorizontalFocusingMirror | Mirror | `XF:10IDD-OP{HFM:1` | HFM | 10-ID-D | source | yes |
| VerticalFocusingMirror | Mirror | `XF:10IDD-OP{VFM:1` | VFM | 10-ID-D | source | yes |
| MultiCrystalMono | Monochromator (?) | `XF:10IDD-OP{MCM:1` | multi-crystal monochromator (analyzer feed) | 10-ID-D | source | yes |
| Analyzer | EnergyAnalyzer (?) | `XF:10IDD-OP{Analy:1-Ax:` | crystal analyzer axes | 10-ID-D | detection | yes |
| Spectrometer | SpectrometerArm (?) | `XF:10IDD-OP{Spec:1-Ax:` | spectrometer arm axes | 10-ID-D | detection | yes |
| Pinhole | Slit (?) | `XF:10IDD-OP{Pinh:1` | pinhole | 10-ID-D | source | yes |
| EndstationSlit5 | Slit | `XF:10IDD-OP{Slt:5` | endstation slit | 10-ID-D | source | yes |
| EndstationSlit4 | Slit | `XF:10IDC-OP{Slt:4` | slit | 10-ID-C | source | yes |
| Table1 | Table | `XF:10IDC-OP{Tbl:1` | endstation table | 10-ID-C | sample | yes |
| SampleEnvironment | TemperatureController (?) | `XF:10IDD-OP{Env:1-Ax:` | sample environment axes | 10-ID-D | sample | yes |
| BeamPositionMonitor1 | GenericProbe (?) | `XF:10IDA-OP{BPM:1` | BPMs (BPM:1/2 + cams) | 10-ID-A | source | yes |

Device-level prefixes read verbatim from source: `Mono:DCM`, `Mono:HRM2`, `HFM:1`/`VFM:1`, `MCM:1`, `Analy:1`, `Spec:1`, `SSA:1`, the BPMs and table.

## Role hints

- **Positioner**: both monos, MCM, HFM/VFM mirrors, slits, pinhole, table, analyzer + spectrometer axes, sample environment.
- **Detector / analyzer**: the crystal Analyzer + Spectrometer arm are the IXS energy-analysis chain.
- **Sensor**: BPMs.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. IXS is a shipped deployment; aligns with `deployments/ixs/`. The survey notes IXS coined a loose EnergyAnalyzer.

## New-family watch

- **EnergyAnalyzer (LOOSE)**: the `Analy:1` crystal analyzer. The survey records IXS as the origin of a loose EnergyAnalyzer family (n=1). Stays loose pending a 2nd hard-IXS/analyzer consumer. Distinct from ElectronAnalyzer (photoemission) and EmissionSpectrometer (XES crystal).
- **SpectrometerArm (LOOSE)**: `Spec:1` arm; same family-string as SIX's RIXS arm? Confirm whether the hard-IXS spectrometer arm and the soft-RIXS arm are one family or two. This is a graduation-clarification, not a coin.
- **MCM -> Monochromator (?)**: multi-crystal mono feeding the analyzer; confirm Monochromator binding.
- **Monochromator (DCM/HRM2)**, **Mirror (HFM/VFM)**, **Table**: bind to graduated families directly.

## Deferred / absent

- The analyzer/spectrometer internal crystal axes are an Asset here; per-crystal decomposition is confirm-pending detail.
- **SampleEnvironment -> TemperatureController (?)**: confirm settable.
- The **insertion-device source** referenced via `10-machine.py`; no standalone InsertionDevice instantiated; carry `SRC-1`.
