# Extracted facts: IOS (23-ID-2)

Candidate device facts for `ios` (NSLS-II 23-ID-2, in-situ / operando soft X-ray spectroscopy: ambient-pressure XPS / AP-PES, NEXAFS / XAS). Candidates only; confirm every row before modeling. Source: the public `NSLS2/ios-profile-collection` (`startup/*.py`, read 2026-06; modules `01-classes`, `10-machine`, `10-optics`, `11-valves`, `20-detectors`, `21-specs_analyzer`, `22-xspress3`, `23-devices`). Every value is carried `confirm` until IOS staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Soft X-ray photoemission; twin of CSX on the 23-ID straight"
    IOS shares the canted 23-ID straight with CSX. It is a soft X-ray beamline: EPU insertion devices (variable polarization), a grating monochromator, KB refocusing, and a SPECS hemispherical electron analyzer for ambient-pressure photoemission. The ElectronAnalyzer family (graduated via ESM/SST) applies here.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:23ID-PPS{Sh:FE}` | (PPS shutter) | 23-ID | source | yes |
| PhotonShutter | Shutter | `XF:23ID2-PPS{PSh}` | (PPS shutter; + PPS:2) | 23-ID-2 | source | yes |
| InsertionDevice1 | InsertionDevice | `XF:23ID-ID{EPU:1` | EPU variable-polarization undulator 1 | 23-ID | source | yes |
| InsertionDevice2 | InsertionDevice | `XF:23ID-ID{EPU:2` | EPU undulator 2 (canted straight) | 23-ID | source | yes |
| GratingMonochromator | GratingMonochromator | `XF:23ID2-OP{Mono` | soft X-ray grating mono | 23-ID-2 | source | yes |
| Mirror3B | Mirror | `XF:23ID2-OP{Mir:3B` | mirror 3B axes | 23-ID-2 | source | yes |
| KBMirrorHorizontal | Mirror | `XF:23ID2-OP{KB:MirH-Ax:` | KB horizontal refocus | 23-ID-2 | source | yes |
| KBMirrorVertical | Mirror | `XF:23ID2-OP{KB:MirV-Ax:` | KB vertical refocus | 23-ID-2 | source | yes |
| KBPinhole | Slit (?) | `XF:23ID2-OP{KB:Pnh-Ax:` | KB pinhole | 23-ID-2 | source | yes |
| EntranceSlit1 | Slit | `XF:23ID2-OP{Slt:1` | entrance slit | 23-ID-2 | source | yes |
| ExitSlit2 | Slit | `XF:23ID2-OP{Slt:2-Ax:` | exit slit | 23-ID-2 | source | yes |
| DiagnosticModule1 | LinearStage | `XF:23ID2-OP{DM1-Ax:` | DM1 (+ FS, HSlt sub-stages) | 23-ID-2 | source | yes |
| DiagnosticModule2 | LinearStage | `XF:23ID2-OP{DM2:Slt-Ax:` | DM2 slit (+ FS, FSPhDiod) | 23-ID-2 | source | yes |
| SPECSAnalyzer | ElectronAnalyzer | `XF:23ID2-ES{SPECS}` | SPECS hemispherical analyzer (+ SPECS-PS1 power supply) | 23-ID-2 | detection | yes |
| APPESCell | LinearStage | `XF:23ID2-ES{APPES:1-Ax:` | ambient-pressure PES cell stage | 23-ID-2 | sample | yes |
| VortexDetector | EnergyDispersiveSpectrometer | `XF:23ID2-ES{Vortex}` | Vortex SDD (+ BI Vortex:1 stage) | 23-ID-2 | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:23ID2-ES{Xsp:1}` | Xspress3 | 23-ID-2 | detection | yes |
| CurrentAmplifiers | GenericProbe (?) | `XF:23ID2-ES{CurrAmp:1}` | current amplifiers 1/2/3 | 23-ID-2 | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:23ID2-ES{Sclr:1}` | scaler channels | 23-ID-2 | detection | yes |
| GoldMesh | FluxMonitor (?) | `XF:23ID2-BI{AuMesh:1-Ax:` | Au-mesh I0 monitor | 23-ID-2 | detection | yes |
| XASIonChamber | FluxMonitor (?) | `XF:23ID2-BI{IOXAS:1-Ax:` | XAS I0 chamber | 23-ID-2 | detection | yes |
| DiagnosticStages | LinearStage | `XF:23ID2-BI{Diag:1-Ax:` | Diag:1/3/4 diagnostic stages | 23-ID-2 | source | yes |
| GateValves | GenericProbe (?) | `XF:23ID2-VA{APPES-GV:3}` | gate valves (APPES-GV, Diag-GV) | 23-ID-2 | vacuum | yes |

Device-level prefixes read verbatim from source: the `EPU:1/EPU:2` insertion devices, `Mono` grating, `KB:MirH/MirV/Pnh`, `SPECS` + `SPECS-PS1`, `APPES:1`, `Vortex`/`Xsp:1`, `AuMesh:1`/`IOXAS:1` I0 monitors.

## Role hints

- **Positioner**: grating mono, mirror 3B, KB mirrors + pinhole, slits, diagnostic modules, APPES cell stage.
- **Source**: two EPU insertion devices (variable polarization, a controllable axis for the soft X-ray dichroism work).
- **Sensor**: Au mesh + XAS ion chamber (I0/flux), current amplifiers, scaler.
- **Detector / analyzer**: SPECS hemispherical electron analyzer (photoemission), Vortex + Xspress3 SDD.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration, the layer CORA would replace. IOS is the CSX twin on the canted 23-ID straight; aligns with `deployments/ios/`.

## New-family watch

No new coining. Strong confirmations:
- **SPECSAnalyzer -> ElectronAnalyzer** (graduated via ESM + SST): IOS is a further consumer. Bind directly. This is a clean photoemission-family reuse beyond ARPES (here ambient-pressure XPS).
- **GratingMonochromator** (graduated via CSX): IOS is another soft X-ray consumer. Bind directly.
- **EPU -> InsertionDevice** (catalog): two variable-polarization undulators; polarization as a controllable axis (the i06/i10/ESM pattern). Bind directly.
- **VortexDetector + Xspress3 -> EnergyDispersiveSpectrometer** (graduated): bind directly.
- **GoldMesh / XASIonChamber -> FluxMonitor (?)**: I0 monitors; intensity side FluxMonitor, confirm. **CurrentAmplifiers / Scaler / GateValves -> GenericProbe (loose)**.

## Deferred / absent

- The SPECS analyzer's internal lens/energy axes are not fully decomposed here (the analyzer is an Asset; its scan axes are confirm-pending detail).
- Gate-valve vacuum devices (`11-valves.py`) partly mapped; deferred `VAC-1`.
- Note the shared 23-ID straight: EPU + front-end PVs are at `XF:23ID-*` (shared with CSX), the IOS-specific devices at `XF:23ID2-*`; confirm the canted-straight source sharing with staff.
