# Extracted facts: TES (8-BM)

Candidate device facts for `tes` (NSLS-II 8-BM, Tender Energy X-ray absorption Spectroscopy: tender-energy XAS / XRF microprobe). Candidates only; confirm every row before modeling. Source: the public `NSLS2/tes-profile-collection` (`startup/*.py`, read 2026-06; modules `15-machine`, `20-motors`, `22-shutters`, `25-sclr`, `26-areadetectors`, `27-Teledyne_PICAM`, `27-xspress3`). Every value is carried `confirm` until TES staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Tender-energy microprobe; KB refocus"
    TES covers the tender X-ray range (roughly 2-5 keV) with a scanning mono, KB-mirror microfocus, and a fly-scanning XRF map (Xspress3 SDD). The sample environment lives in the SE (sample-environment) sub-namespace at 8-BM-C.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PhotonShutter | Shutter | `XF:08BMES-PPS{PSh}` | (PPS shutter) | 8-BM-ES | source | yes |
| Monochromator | Monochromator | `XF:08BMA-OP{Mono:1-Ax:` | scanning mono axes | 8-BM-A | optics | yes |
| FocusingMirror | Mirror | `XF:08BMA-OP{Mir:FM-Ax:` | FM mirror axes | 8-BM-A | optics | yes |
| KBMirrorHorizontal | Mirror | `XF:08BMES-OP{Mir:KBH-Ax:` | KB horizontal refocus | 8-BM-ES | optics | yes |
| KBMirrorVertical | Mirror | `XF:08BMES-OP{Mir:KBV-Ax:` | KB vertical refocus | 8-BM-ES | optics | yes |
| SecondarySourceAperture | Slit | `XF:08BMES-OP{SSA:1-Ax:` | SSA blade axes | 8-BM-ES | optics | yes |
| SlitModule | Slit | `XF:08BMES-OP{SM:1-Ax:` | slit module axes | 8-BM-ES | optics | yes |
| SampleStage | LinearStage | `XF:08BMC-ES:SE{Smpl:1-Ax:` | sample positioning | 8-BM-C | sample | yes |
| SampleMotionStage | LinearStage | `XF:08BMC-ES:SE{SmplM:1-Ax:` | sample fly-scan motion | 8-BM-C | sample | yes |
| DetectorStage | LinearStage | `XF:08BMC-ES:SE{Det:1-Ax:` | detector positioning | 8-BM-C | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:08BM-ES{Xsp:2}` | Xspress3 SDD (+ XS3:Det-3) | 8-BM | detection | yes |
| PICAMDetector | Camera | `XF:08BM-ES{Det:PICAM1}` | Teledyne PICAM detector | 8-BM | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:08BM-ES:1{Sclr:1}` | scaler channels | 8-BM | detection | yes |
| IonChamber | FluxMonitor (?) | `XF:08BM-ES{IO:2}` | I0 ion chamber | 8-BM | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:08BMES-BI{PSh:1-BPM:3}` | BPM 3/4 | 8-BM-ES | diagnostics | yes |
| AxisCamera | GenericProbe (?) | `XF:08BM-BI{Axis-Cam:1}` | viewing cameras (1/2, Cam:6/7) | 8-BM | sample | yes |
| EndstationMotionController | MotionController | `XF:08BM-CT{MC:06}` | motion controller | 8-BM | sample | yes |

Device-level prefixes read verbatim from source: `Mono:1`, `Mir:FM`, the `Mir:KBH/KBV` KB pair, `SSA:1`, the SE sample stages, `Xsp:2`/`XS3:Det-3`, `Det:PICAM1`.

## Role hints

- **Positioner**: mono, FM mirror, KB mirrors, SSA, slit module, sample/sample-motion/detector stages.
- **Sensor**: ion chamber (I0), scaler, BPMs.
- **Detector**: Xspress3 (XRF), PICAM.
- **Fly-scan**: the sample-motion stage + scaler/Xspress3 raster the XRF map.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration, the layer CORA would replace. TES is a tender-energy sibling to the harder-XAS beamlines (ISS/QAS/BMM).

## New-family watch

No new coining. Notes:
- **KB mirrors -> Mirror** (graduated), **Xspress3 -> EnergyDispersiveSpectrometer** (graduated): bind directly.
- **IonChamber -> FluxMonitor (?)** (graduated): confirm the `IO:2` device is the I0 chamber.
- **Scaler / BPM / AxisCam -> GenericProbe (loose)**: held DIAG-1.
- **PICAM -> Camera**: a CMOS-style detector; bind Camera.

## Deferred / absent

- **vstream-cam** (`27-vstream-cam.py`) video-stream camera and **ROIs** (`10-rois.py`) partly mapped; deferred `DET-1`.
- **Bending-magnet source** (`15-machine.py`) status only; no standalone InsertionDevice; carry `SRC-1`.
- Note the SE (sample-environment) sub-namespace at 8-BM-C may carry temperature/flow devices not isolated here (`ENV-1`).
