# Extracted facts: CHX (11-ID)

Candidate device facts for `chx` (NSLS-II 11-ID, coherent hard X-ray scattering: XPCS, SAXS/WAXS, GISAXS). Candidates only; confirm every row before modeling. Source: the public `NSLS2/chx-profile-collection` (`startup/*.py`, read 2026-06; modules `10-optics`, `15-machines`, `20-area-detectors`, `25-shutter`, `26-scalers`, `31-syringe_pump`, `35-detectors`, `51_Linkam`, `97_HDM`, `98-xspress3`, `991-delaygenerator`). Every value is carried `confirm` until CHX staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:11ID-PPS{Sh:FE}` | (PPS shutter) | 11-ID-A | source | yes |
| PhotonShutter | Shutter | `XF:11IDA-PPS{PSh}` | (PPS shutter) | 11-ID-A | source | yes |
| Monochromator | Monochromator | `XF:11IDA-OP{Mono:DCM` | Si DCM (coherent beam) | 11-ID-A | optics | yes |
| MultilayerMono | Monochromator | `XF:11IDA-OP{Mono:DMM` | double-multilayer mono (higher flux mode) | 11-ID-A | optics | yes |
| HorizontalDeflectingMirror | Mirror | `XF:11IDA-OP{Mir:HDM` | pitch=`-Ax:P}Pos-I`; jacks (HDM) | 11-ID-A | optics | yes |
| Transfocator | Transfocator | `XF:11IDA-OP{Lens:` | CRL lens stack | 11-ID-A | optics | yes |
| Filter | Filter | `XF:11IDA-OP{Flt:1-Ax:` | y=`Y}Mtr` | 11-ID-A | optics | yes |
| MonoBeamSlit | Slit | `XF:11IDA-OP{Slt:MB` | blade axes | 11-ID-A | optics | yes |
| PinkBeamSlit | Slit | `XF:11IDA-OP{Slt:PB` | blade axes | 11-ID-A | optics | yes |
| Diffractometer | Diffractometer (?) | `XF:11IDB-ES{Dif` | xh=`-Ax:XH}Mtr`; zh=`-Ax:ZH}Mtr` | 11-ID-B | sample | yes |
| SAXSTable | Table | `XF:11IDB-ES{Tbl:SAXS-Ax:` | m1/m2/x1/x2 | 11-ID-B | detection | yes |
| SampleBeamStop | BeamStop | `XF:11IDB-OP{BS:Samp` | x=`-Ax:X}Mtr`; y=`-Ax:Y}Mtr` | 11-ID-B | sample | yes |
| SAXSBeamStop | BeamStop | `XF:11IDB-ES{BS:SAXS` | beamstop axes | 11-ID-B | detection | yes |
| Linkam | TemperatureController | `XF:11ID-ES{LINKAM}:` | TEMP/SETPOINT:SET/RAMPRATE:SET/STARTHEAT/STATUS | 11-ID-B | sample | yes |
| SyringePump | FlowController | `XF:11IDB-ES{Pmp:` | Run/Stop/Purge cmds per pump | 11-ID-B | sample | yes |
| Eiger1M | Camera | `XF:11IDB-ES{Det:Eig1M}` | Eiger 1M area detector | 11-ID-B | detection | yes |
| Eiger4M | Camera | `XF:11IDB-ES{Det:Eig4M}` | Eiger 4M area detector | 11-ID-B | detection | yes |
| Eiger500K | Camera | `XF:11IDB-ES{Det:Eig500K}` | Eiger 500K (fast XPCS) | 11-ID-B | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:11IDB-ES{Xsp:1}:` | Xspress3 | 11-ID-B | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:11IDB-ES{Sclr:1}` | scaler channels | 11-ID-B | detection | yes |
| Zebra | TimingController (?) | `XF:11IDB-ES{Zebra}:` | fly-scan / detector gating | 11-ID-B | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:11IDA-BI{Bpm:1` | beam position cam/monitor | 11-ID-A | diagnostics | yes |
| AH401BElectrometer | FluxMonitor (?) | `XF:11IDA-BI{AH401B}` | 4-channel electrometer | 11-ID-A | diagnostics | yes |

Device-level prefixes read verbatim from source (`Mono:DCM`/`Mono:DMM`, `Mir:HDM`, `Lens:`, the `LINKAM` block, `Pmp:` syringe commands, the three Eiger dets, `Zebra`, `Dif`, `Tbl:SAXS`).

## Role hints

- **Positioner**: both monos, HDM mirror, transfocator, filter, slits, diffractometer, SAXS table, both beamstops.
- **Sensor**: AH401B electrometer, scaler, BPM.
- **Detector**: Eiger 1M/4M/500K, Xspress3.
- **Regulator**: Linkam (TEMP readback + SETPOINT/RAMPRATE setpoints + STARTHEAT) is a settable-continuous-setpoint thermal actuator, the TemperatureController/Regulator signature.
- **Flow actuator**: SyringePump (Run/Stop/Purge) is a FlowController.
- **Timing**: Zebra + the delay generator (`991-delaygenerator.py`) gate fast XPCS acquisition.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration, the layer CORA would replace.

## New-family watch

No new coining. Confirmations / graduation watches:
- **Transfocator** (graduated catalog Family): CHX is a confirmed consumer (the survey lists chx in the CRL rule-of-three). Bind directly.
- **Linkam -> TemperatureController** (graduated, presents Regulator): CHX is another consumer. Bind directly. Note the source also exposes a `XF:11BM-ES:{LINKAM}` prefix (a shared/sibling copy); the CHX device is the `XF:11ID-ES{LINKAM}` one, confirm with staff.
- **SyringePump -> FlowController** (graduation candidate, n=4 per the diamond memo: i22/7-bm/lix/xfp): CHX is a further consumer, reinforcing the overdue FlowController graduation. Flag for the recurrence pass.
- **Diffractometer (?)**: `Dif` exposes only xh/zh here (a 2-axis detector positioner, not a full Euler cradle); confirm whether it is the catalog Diffractometer or a LinearStage. Held.
- **Zebra -> TimingController (?)**: same fly-scan gating question as SRX/ISS; recurring across the fleet, a graduation watch.

## Deferred / absent

- **Delay generator** (`991-delaygenerator.py`) and **point detectors** (`93-point_detector.py`) present; not fully mapped, deferred `DET-1`.
- **Stinger** (`31-stinger.py`) and **commissioning** (`36-commisionning.py`) devices not mapped (`MISC-1`).
- The **insertion-device source** referenced via `15-machines.py` status PVs; no standalone InsertionDevice instantiated; carry `SRC-1`.
