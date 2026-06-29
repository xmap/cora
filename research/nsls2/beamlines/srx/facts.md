# Extracted facts: SRX (5-ID)

Candidate device facts for `srx` (NSLS-II 5-ID, submicron X-ray fluorescence microprobe: XRF mapping, XANES, XRF-tomography). Candidates only; confirm every row before modeling. Source: the public `NSLS2/srx-profile-collection` (`startup/*.py`, read 2026-06; modules `10-machine`, `11-optics`, `15-microES`, `16-nanoES`, `20-diagnostics`, `30-scaler`, `31-xspress3`, `33-36` detectors). Every value is carried `confirm` until SRX staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Two endstations"
    SRX has two experimental endstations sharing one optics train: the micro-focus station (microES, KB-mirror focused) and the nano-focus station (nanoES, a separate nano-KB + PicoScale / fine-positioning stack). Both are modeled below; they share the 5-ID-A/B optics and split at 5-ID-D.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| WhiteBeamShutter | Shutter | `XF:05ID-PPS{Sh:WB}` | (PPS shutter) | 5-ID-A | source | yes |
| PhotonShutter2 | Shutter | `XF:05IDA-PPS:1{PSh:2}` | (PPS shutter) | 5-ID-A | source | yes |
| PhotonShutter4 | Shutter | `XF:05IDB-PPS:1{PSh:4}` | (PPS shutter) | 5-ID-B | source | yes |
| FastShutter | Shutter | `XF:05IDD{FS:1}` | Open-Cmd / Close-Cmd / Status | 5-ID-D | source | yes |
| WhiteBeamSlit | Slit | `XF:05IDA-OP:1{Slt:1-Ax:` | blade axes (SRXSlitsWB) | 5-ID-A | optics | yes |
| PinkBeamSlit | Slit | `XF:05IDA-OP:1{Slt:2-Ax:` | blade axes (SRXSlitsPB) | 5-ID-A | optics | yes |
| HorizontalFocusingMirror | Mirror | `XF:05IDA-OP:1{Mir:1-Ax:` | fine_pitch=`PF}` (E-SP/E-I); jacks (SRXHFM) | 5-ID-A | optics | yes |
| Monochromator | Monochromator | `XF:05IDA-OP:1{Mono:HDCM-Ax:` | p=`P}Mtr`; x2=`X2}Mtr`; piezo roll/pitch (PVPositionerPC); bragg | 5-ID-A | optics | yes |
| SSASlit | Slit | `XF:05IDB-OP:1{Slt:SSA-Ax:` | x (ssa_ob/ssa_ib blades), gap/center calc (SRXSSACalc) | 5-ID-B | optics | yes |
| KBSlit | Slit | `XF:05IDD-OP:1{Slt:KB-Ax:` | blade axes | 5-ID-D | optics | yes |
| MicroSampleStage | LinearStage | `XF:05IDD-ES:1{Det:3-Ax:` | micro-station sample/det axes | 5-ID-D | sample | yes |
| NanoKBHorizontal | Mirror | `XF:05IDD-ES:1{nKB:horz-Ax:` | x=`X}Mtr`; pc=`PC}`; pfpi=`PFPI}Mtr` | 5-ID-D | optics | yes |
| NanoKBVertical | Mirror | `XF:05IDD-ES:1{nKB:vert-Ax:` | y=`Y}Mtr`; pc=`PC}`; pfpi=`PFPI}Mtr` | 5-ID-D | optics | yes |
| NanoSampleStage | LinearStage | `XF:05IDD-ES:1{nKB:Smpl-Ax:` | sx/sy/sz; ssx/ssy/ssz (fine); th/xth/zth | 5-ID-D | sample | yes |
| NanoDetectorStage | LinearStage | `XF:05IDD-ES:1{nKB:Det-Ax:` | x/y/z=`{X,Y,Z}}Mtr`; dist=`Dist}MTR` | 5-ID-D | detection | yes |
| NanoVisualMicroscope | Microscope (?) | `XF:05IDD-ES:1{nKB:VLM-Ax:` | x=`X}Mtr` | 5-ID-D | sample | yes |
| PicoScale | GenericProbe (?) | `XF:05IDD-ES:1{PICOSCALE:1}` | interferometric position metrology | 5-ID-D | diagnostics | yes |
| IonChamber | FluxMonitor | `XF:05IDA-BI:1{IM:1}Int-I` | I0 ion chamber current | 5-ID-A | detection | yes |
| Preamps | GenericProbe (?) | `XF:05IDD-CT{SR570:1}` / `{SR570:2}` / `{SR570:3}` | SR570 current preamps (I0/Im/It) | 5-ID-D | detection | yes |
| QuadEMBPM | FluxMonitor (?) | `XF:05ID-BI{EM:BPM1}` / `{EM:BPM2}` | NSLS-II electrometer BPMs | 5-ID-A | diagnostics | yes |
| AH501BPM | GenericProbe (?) | `XF:05IDA-BI{BPM:01}AH501:` / `{BPM:02}` / `{BPM:05}` | AH501 4-channel current BPMs | 5-ID-A | diagnostics | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:05IDD-ES{Xsp:3}:` | Xspress3 (SDD fluorescence MCA) | 5-ID-D | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:05IDD-ES:1{Sclr:1}` | scaler channels | 5-ID-D | detection | yes |
| Zebra | TimingController (?) | `XF:05IDD-ES:1{Dev:Zebra1}` | fly-scan pulse/gate generator | 5-ID-D | detection | yes |
| MerlinDetector | Camera | `XF:05IDD-ES{Merlin:1}` | Merlin photon-counting area detector | 5-ID-D | detection | yes |
| DexelaDetector | Camera | `XF:05IDD-ES{Dexela:1}` | Dexela flat-panel (XRD) | 5-ID-D | detection | yes |
| EigerDetector | Camera | `XF:05IDD-ES{Det:Eig1M}` | Eiger 1M area detector | 5-ID-D | detection | yes |

The device-level prefixes above are read verbatim from source (`dcm = SRXDCM("XF:05IDA-OP:1{Mono:HDCM-Ax:")`, `hfm = SRXHFM("XF:05IDA-OP:1{Mir:1-Ax:")`, `slt_wb/slt_pb/slt_ssa`, the nanoES `nKB:*` axes, the diagnostics SR570 / AH501 / EM blocks). Several optics axes are built from `format`-string suffixes in source, so the per-axis `}Mtr` leaf is shown where it is a literal and described where it is composed.

## Role hints

- **Positioner**: all slits, both mirrors (HFM + nano-KB horz/vert), the HDCM (with piezo roll/pitch `PVPositionerPC`), micro and nano sample stages, nano detector stage, VLM. Mix of `EpicsMotor`, `PVPositionerPC`, and custom `Device` subclasses.
- **Sensor**: IonChamber (I0), the SR570 preamps, the EM/AH501 BPMs, the scaler, the PicoScale interferometer.
- **Detector**: FluorescenceSpectrometer (Xspress3 SDD), Merlin, Dexela, Eiger.
- **Controller / timing**: Zebra (fly-scan gating), the `FbPid` feedback PIDs in optics (`XF:05IDD-CT{FbPid:01/02}`) which steer beam position, a Controller-role hint not yet a device here.

## Trust hints

`startup/user_group_permissions.yaml` (1.65 KB) present: the queue-server permission model. SRX runs `91-queueserver.py`. Confirms the bluesky queue-server is the orchestration layer CORA would replace, consistent with the NSLS-II survey.

## New-family watch

Nothing to coin. Loose / fallback bindings to flag, none meeting rule-of-three from SRX alone:

- **Zebra -> TimingController (?)**: the fly-scan pulse/gate generator. TimingController is a catalog Family; confirm the Zebra presents it (vs a bare GenericProbe). PandABox/Zebra timing recurs across NSLS-II fly-scanning beamlines, a graduation watch but not coined here.
- **PicoScale / AH501 / SR570 -> GenericProbe (loose)**: position metrology and current preamps. Same fragmentation as the fleet-wide beam-position question (`DIAG-1`); stay loose.
- **NanoVisualMicroscope -> Microscope (?)**: an on-axis visual-light microscope for sample viewing, not the X-ray Microscope Family sense; confirm before binding (likely a Camera + stage, not Microscope).
- **QuadEMBPM -> FluxMonitor (?)**: the `EM:BPM` electrometers read both position and intensity; the intensity/I0 side is FluxMonitor, the position side is the held DIAG-1 question. Split per use at modeling time.

## Deferred / absent

- **Cryocooler** (`13-cryocooler.py`) and **temp stages** (`18-tempstages.py`) exist in source but were not device-mapped in this pass; the temp stages are a possible Regulator-presenting candidate (TemperatureController lineage) and should be read before a deployment scaffold (`TEMP-1`).
- **Qmini spectrometer** (`37-Qmini.py`), **PCO** (`33-pco.py`), **confocal** (`66-confocal.py`), **full-field** (`65-fullfield.py`) modes are present; not mapped here, deferred as `MODE-1` until the deployment needs them.
- The **undulator source** is referenced via machine status PVs (`XF:05IDA-CT{IOC:Status01}`) but no standalone InsertionDevice device is instantiated in the read modules; carry as `SRC-1`.
