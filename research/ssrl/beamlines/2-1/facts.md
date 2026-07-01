# Extracted facts: SSRL 2-1

Candidate device facts for `2-1` (SSRL beamline 2-1, powder / single-crystal diffraction; high-throughput combinatorial diffraction). Candidates only; confirm every row before modeling. Source: the public `tangkong/SSRL-2-1` bluesky profile (`profile_bluesky/startup/instrument/devices/*.py`, read 2026-06). Every value is carried `confirm` until SSRL staff verify it: the profile is strong evidence, not a CORA-owned fact.

!!! warning "Template-derived PVs: placeholder vs real"
    The SSRL-2-1 profile was cloned from the `SSRL-X-X` template and is partly customized. The sample-stage motors carry **`BL00:` prefixes** (`BL00:IMS:MOTOR1-4`, `BL00:PICOD1:MOTOR2-3`), which is a generic/shared crate or a template default, NOT a confirmed `BL21:` beamline-2-1 namespace; the detectors carry a mix of **real** roots (`BL15:PILATUS300K:`, `BL15:MARCCD:`, `SSRL:DEX2923:`) and **example** roots (`XSPRESS3-EXAMPLE:`). Every PV below is recorded exactly as it appears in source, with the placeholder/example status flagged. This is the honest state: the profile is real bluesky source but the PV namespace needs staff confirmation (PV-1).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV (as in source), dodal/ophyd class as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV (as in source) | ophyd class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| SampleStage | LinearStage | `BL00:IMS:MOTOR2/3/4` (px/py/pz), `BL00:IMS:MOTOR1` (th) | HiTpStage(MotorBundle) of EpicsMotor | sample | yes (PV-1: BL00 placeholder) |
| ViewerStage | LinearStage | `BL00:PICOD1:MOTOR2/3` (vx/vy) | EpicsMotor | sample | yes (PV-1) |
| PilatusDetector | Camera | `BL15:PILATUS300K:` | PilatusDetector | detection | yes |
| MarCCDDetector | Camera | `BL15:MARCCD:` | MarCCD | detection | yes |
| DexelaDetector | Camera | `SSRL:DEX2923:` | Dexela | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XSPRESS3-EXAMPLE:` (example root) | Xspress3 | detection | yes (PV-1: example root) |
| RIOAnalogIO | GenericProbe (?) | `BL00:RIO.AI0-3`, `BL00:RIO.AO1-4`, `BL00:RIO.DO00-01` | EpicsSignal (NI RIO crate) | source | yes (PV-1) |

Device-level handles read verbatim from source: the `HiTpStage` MotorBundle (`BL00:IMS:MOTOR1-4`, `BL00:PICOD1:MOTOR2-3`), `PilatusDetector("BL15:PILATUS300K:")`, `MarCCD("BL15:MARCCD:")`, `Dexela("SSRL:DEX2923:")`, the RIO analog/digital channels.

## Role hints

- **Positioner**: the HiTp sample stage (px/py/pz + theta) and viewer stage; all `EpicsMotor`.
- **Sensor**: the NI RIO crate analog/digital IO (intensity / shutter signals).
- **Detector**: Pilatus 300K + MarCCD + Dexela (diffraction area detectors), Xspress3 (fluorescence).

The "HiTp" naming (High-Throughput) confirms the combinatorial / high-throughput diffraction technique: a sample stage rastering a library plate under area detectors.

## Trust hints

bluesky profile (ipython startup + `instrument` package + `happi/db.json`); no queue-server permission file. The bluesky RunEngine is the orchestration layer CORA would conduct over.

## New-family watch

No new coining:
- **Pilatus / MarCCD / Dexela -> Camera** (graduated): three diffraction area detectors; bind directly.
- **Xspress3 -> EnergyDispersiveSpectrometer** (graduated): bind directly (example PV root, confirm).
- **HiTp stage -> LinearStage** (graduated): a multi-axis sample-positioning stage for high-throughput rastering; LinearStage (the th axis could be a RotaryStage component, confirm).
- **RIO crate -> GenericProbe (loose)**: NI RIO analog/digital IO; the DIAG-1 cluster.

## Deferred / absent

- **PV-1 (the headline):** the motor PV namespace is `BL00:` (placeholder/shared) and the Xspress3 root is an example string; the real BL2-1 PV prefixes need staff confirmation. Detectors carry plausibly-real `BL15:`/`SSRL:` roots but note `BL15` would be beamline 15, not 2-1, so even those need confirmation (possibly shared detectors or a mis-customized clone).
- **MONO-1 / OPTICS-1:** the monochromator, mirrors, slits, and beam optics are not in the profile (the bluesky profile is endstation-focused); open questions.
- PSS / hutch safety and passive beam-path tier not in the profile (SCOPE-1).
