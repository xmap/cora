# Extracted facts: HXN (3-ID)

Candidate device facts for `hxn` (NSLS-II 3-ID, scanning hard X-ray nanoprobe: nano-XRF, ptychography, nano-tomography). Candidates only; confirm every row before modeling. Source: the public `NSLS2/hxn-profile-collection` (`startup/*.py`, read 2026-06; modules `10-optics`, `11-machine`, `12-endstation`, `13-mll`, `15-zp`, `20-detectors`, `20-eiger`, `21-xspress3`, `22-scalers`, `23-interferometers`, `61-nano-es`, `64-nano-merlin`). Every value is carried `confirm` until HXN staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Dual nanofocus: MLL and zone plate"
    HXN's signature is two interchangeable nanofocusing optics, each with its own piezo-driven sample-scanning stack: a multilayer Laue lens (MLL) and a Fresnel zone plate (ZP). The fine scanning axes run on dedicated piezo / coordinate-system controllers (Ppmac, ZpPI, ANC350, MCS), distinct from the coarse stages. This is the densest motion topology in the fleet so far.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PhotonShutter | Shutter | `XF:03IDB-PPS{PSh}` | (PPS shutter) | 3-ID-B | source | yes |
| FluorescenceScreen | Screen | `XF:03IDA-OP{FS:1-Ax:` | y=`Y}Mtr` | 3-ID-A | diagnostics | yes |
| Monochromator | Monochromator | `XF:03IDA-OP{Mon:1-Ax:` | bragg=`Bragg}Mtr`; p=`P}Mtr`; pf=`PF}Mtr` | 3-ID-A | optics | yes |
| HorizontalCollimatingMirror | Mirror | `XF:03IDA-OP{HCM:1-Ax:` | pf=`PF}Mtr` | 3-ID-A | optics | yes |
| HorizontalFocusingMirror | Mirror | `XF:03IDA-OP{HFM:1-Ax:` | pf=`PF}Mtr` | 3-ID-A | optics | yes |
| Mirror1 | Mirror | `XF:03IDA-OP{Mir:1-Ax:` | p=`P}Mtr`; bend=`Bend}Mtr`; x/y | 3-ID-A | optics | yes |
| Mirror2 | Mirror | `XF:03IDA-OP{Mir:2-Ax:` | p/bend/x | 3-ID-A | optics | yes |
| VerticalMirrorSystem | Mirror | `XF:03IDA-OP{VMS:1-Ax:` | VMS axes | 3-ID-A | optics | yes |
| Transfocator | Transfocator | `XF:03IDA-OP{Lens:CRL` | CRL lens stack | 3-ID-A | optics | yes |
| WhiteBeamSlit1 | Slit | `XF:03IDA-OP{Slt:1` | blade axes | 3-ID-A | optics | yes |
| WhiteBeamSlit2 | Slit | `XF:03IDA-OP{Slt:2` | blade axes | 3-ID-A | optics | yes |
| SecondarySourceAperture | Slit | `XF:03IDB-OP{Slt:SSA1` | SSA blade axes | 3-ID-B | optics | yes |
| MLLScanStage | LinearStage | `XF:03IDC-ES{MCS:1-Ax:` | mlldiffy + MLL fine axes (coordinate system 1) | 3-ID-C | sample | yes |
| ZPScanStage | LinearStage | `XF:03IDC-ES{MCS:2-Ax:` | zpx/zpy/zpz (coordinate system 2) | 3-ID-C | sample | yes |
| ZPPiezoSample | LinearStage | `XF:03IDC-ES{Ppmac:1-` | zpssx/zpssy/zpssz fine piezo (PowerPMAC) | 3-ID-C | sample | yes |
| ZPPiezoInterfero | LinearStage | `XF:03IDC-ES{ZpPI:1-` | zpsx/zpsz (PI piezo) | 3-ID-C | sample | yes |
| AttocubePositioners | LinearStage | `XF:03IDC-ES{ANC350:` | ANC350:1-8 Attocube coarse axes | 3-ID-C | sample | yes |
| Diffractometer | Diffractometer (?) | `XF:03IDC-ES{Diff` | diffraction stage (MCS:3 diffsth) | 3-ID-C | sample | yes |
| Eiger1M | Camera | `XF:03IDC-ES{Det:Eiger1M}` | Eiger 1M (ptychography) | 3-ID-C | detection | yes |
| Merlin1 | Camera | `XF:03IDC-ES{Merlin:1}` | Merlin photon-counting | 3-ID-C | detection | yes |
| Merlin2 | Camera | `XF:03IDC-ES{Merlin:2}` | second Merlin | 3-ID-C | detection | yes |
| DexelaDetector | Camera | `XF:03IDC-ES{Dexela:1}` | Dexela flat-panel | 3-ID-C | detection | yes |
| VortexDetector | EnergyDispersiveSpectrometer | `XF:03IDC-ES{Det:Vort` | Vortex SDD (nano-XRF) | 3-ID-C | detection | yes |
| BrukerDetector | EnergyDispersiveSpectrometer (?) | `XF:03IDC-ES{Det:Bruk` | Bruker SDD | 3-ID-C | detection | yes |
| DXPController | GenericProbe (?) | `XF:03IDC-ES{DXP:1}` | DXP pulse processor | 3-ID-C | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:03IDC-ES{Sclr:1}` | scaler channels (Sclr:1-3) | 3-ID-C | detection | yes |
| FiberPositioners | LinearStage (?) | `XF:03IDC-ES{FPS:1` | FPS:1-6 fiber/positioner stages | 3-ID-C | detection | yes |
| Interferometers | GenericProbe (?) | `XF:03IDC-ES{FPS:` | interferometric position metrology (23-interferometers) | 3-ID-C | diagnostics | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:03ID-BI{EM:BPM1}` | EM:BPM1/BPM2 electrometer BPMs | 3-ID-A | diagnostics | yes |
| XeyeCamera | GenericProbe (?) | `XF:03IDB-BI{Xeye-CAM:1}` | on-axis viewing camera | 3-ID-B | sample | yes |

Device-level prefixes read verbatim from source: `Mon:1-Ax:Bragg`, the `HCM:1`/`HFM:1`/`Mir:1`/`Mir:2`/`VMS:1` mirrors, `Lens:CRL`, the MLL/ZP coordinate systems (`MCS:1/2/3`), the piezo controllers (`Ppmac:1`, `ZpPI:1`, `ANC350:1-8`), and the Eiger/Merlin/Dexela/Vortex/Bruker detectors.

## Role hints

- **Positioner**: mono, all mirrors, CRL, slits, and the entire nanofocus motion stack (MLL/ZP coordinate systems, Ppmac + ZpPI + ANC350 piezo/coarse controllers, diffractometer). The densest Positioner set in the fleet.
- **Sensor**: BPM electrometers, scaler, interferometers (position metrology), Xeye.
- **Detector**: Eiger 1M, two Merlins, Dexela (area); Vortex + Bruker (SDD energy-dispersive); DXP (the SDD pulse processor).

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. HXN runs a `nano-fly2d` fly-scanning stack with nano-zebra + nano-panda gating (composed PV prefixes, not isolated in this pass).

## New-family watch

No new coining. Notes:
- **Transfocator** (graduated): HXN is a confirmed CRL consumer; bind directly.
- **VortexDetector / BrukerDetector -> EnergyDispersiveSpectrometer** (graduated): two SDD consumers on one beamline; bind directly. The DXP pulse processor is the analog front-end (GenericProbe loose).
- **The piezo/coordinate-system controllers** (Ppmac, ZpPI, ANC350, MCS) all fold to LinearStage Positioners; do NOT coin per-vendor families. The nanofocus scanning is a motion topology, not new device kinds.
- **Diffractometer (?)**: confirm whether `Diff` is the catalog Diffractometer or a sample-rotation stage.
- **BeamPositionMonitor -> GenericProbe (loose)**: held DIAG-1.

## Deferred / absent

- **nano-zebra** (`66-nano-zebra.py`) and **nano-panda** (`67-nano-panda.py`) fly-scan gating use composed PV prefixes not isolated here; deferred `TIMING-1` (the fleet-wide Zebra/PandA timing question).
- **ptycho** (`16-ptycho.py`) and **bechxn** (`43-bechxn.py`) are analysis/beam-emittance, not devices.
- The **insertion-device source** referenced via `11-machine.py`; no standalone InsertionDevice instantiated; carry `SRC-1`.
