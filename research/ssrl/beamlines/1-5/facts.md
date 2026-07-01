# Extracted facts: SSRL 1-5

Candidate device facts for `1-5` (SSRL beamline 1-5, X-ray scattering / diffraction; high-throughput combinatorial). Candidates only; confirm every row before modeling. Source: the public `tangkong/SSRL-1-5` bluesky profile (`profile_bluesky/startup/instrument/devices/*.py`, read 2026-06). Every value is carried `confirm` until SSRL staff verify it: the profile is strong evidence, not a CORA-owned fact.

!!! warning "Template-derived motor PVs"
    Like the 2-1 profile, SSRL-1-5's sample motors use **`BL00:` placeholders** (`BL00:IMS:MOTOR1-4`, `BL00:PICOD1:MOTOR1-2`) rather than a confirmed `BL15:` beamline namespace; the RIO crate is `HITP:RIO.*` (the high-throughput crate) and the detectors carry real-looking `BL15:` / `SSRL:` roots. PVs recorded exactly as in source, placeholder status flagged (PV-1).

## Device inventory

| Device | Suggested family | PV (as in source) | ophyd class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| SampleStage | LinearStage | `BL00:IMS:MOTOR1-4` | HiTpStage(MotorBundle) of EpicsMotor | sample | yes (PV-1) |
| ViewerStage | LinearStage | `BL00:PICOD1:MOTOR1-2` | EpicsMotor | sample | yes (PV-1) |
| Pilatus1M | Camera | `BL15:PILATUS1M:` | PilatusDetector | detection | yes (BL15 root, confirm) |
| MarCCDDetector | Camera | `BL15:MARCCD:` | MarCCD | detection | yes (confirm) |
| DexelaDetector | Camera | `SSRL:DEX2923:` | Dexela | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | (Xspress3) | Xspress3 | detection | yes |
| RIOAnalogIO | GenericProbe (?) | `HITP:RIO.AI0-3`, `HITP:RIO.AO1-4`, `HITP:RIO.DO00-01` | EpicsSignal (NI RIO crate) | source | yes |

Device-level handles read verbatim from source: the `HiTpStage` MotorBundle, `PilatusDetector("BL15:PILATUS1M:")`, `MarCCD("BL15:MARCCD:")`, `Dexela("SSRL:DEX2923:")`, the `HITP:RIO` crate channels.

## Role hints

- **Positioner**: HiTp sample stage + viewer stage (EpicsMotor).
- **Sensor**: HITP RIO crate analog/digital IO.
- **Detector**: Pilatus 1M + MarCCD + Dexela (scattering area detectors), Xspress3 (fluorescence).

The HiTp naming again indicates high-throughput combinatorial scattering (a library plate rastered under area detectors), the 1-5 sibling of 2-1.

## Trust hints

bluesky profile (ipython + `instrument` package + `happi/db.json`); no queue-server permission file. bluesky RunEngine is the orchestration CORA would conduct over.

## New-family watch

No new coining: Pilatus/MarCCD/Dexela -> Camera (graduated), Xspress3 -> EnergyDispersiveSpectrometer (graduated), HiTp stage -> LinearStage (graduated), RIO crate -> GenericProbe (loose, DIAG-1). This is a reuse-only sibling of 2-1.

## Deferred / absent

- **PV-1:** motor PVs are `BL00:` placeholders, detector roots are `BL15:` (beamline 15, not 1-5); real BL1-5 namespace needs staff confirmation. The shared HiTp tooling (`HITP:RIO`, `SSRL:DEX2923:`) is genuinely shared across the combinatorial beamlines, so some cross-beamline device sharing is expected, confirm.
- **MONO-1 / OPTICS-1:** mono, mirrors, slits absent from the endstation profile.
- PSS / hutch safety and passive beam-path tier not in the profile (SCOPE-1).
