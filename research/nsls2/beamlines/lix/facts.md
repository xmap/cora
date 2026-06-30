# Extracted facts: LIX (16-ID)

Candidate device facts for `lix` (NSLS-II 16-ID, life-science solution scattering: bio-SAXS/WAXS, in-line SEC-SAXS, plus scanning-microbeam). Candidates only; confirm every row before modeling. Source: the public `NSLS2/lix-profile-collection`, read 2026-06. **Provenance note:** the live `startup/*.py` is a thin namespace; the real EPICS device definitions are in `startup.obsolete/*.py` (mislabeled, but the operational `XF:16ID*` PVs confirmed by repo code search), and the fluidic-delivery devices (HPLC, syringe pumps, VICI valves) are in `startup/devices/`. Every value is carried `confirm` until LIX staff verify it.

!!! note "Solution scattering + fluidic delivery; the SEC-SAXS chain"
    LIX's signature is the fluidic sample-delivery chain (HPLC, SEC column, syringe pumps, VICI valves) feeding bio-SAXS/WAXS. The beamline optics (DCM, KB + WBM mirrors, HRM) reuse standard families; the novelty is the solution-delivery seam, modeled as Subject/Supply/Procedure (the MX3 precedent). The HPLC pump reuses FlowController.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| Monochromator | Monochromator | `XF:16IDA-OP{Mono:DCM` | DCM axes | 16-ID-A | optics | yes |
| WhiteBeamMirror | Mirror | `XF:16IDA-OP{Mir:WBM` | white-beam mirror | 16-ID-A | optics | yes |
| KBMirrorHorizontal | Mirror | `XF:16IDA-OP{Mir:KBH` | KB horizontal (+ KB-PS) | 16-ID-A | optics | yes |
| KBMirrorVertical | Mirror | `XF:16IDA-OP{Mir:KBV` | KB vertical | 16-ID-A | optics | yes |
| WhiteBeamSlit1 | Slit | `XF:16IDA-OP{Slt:1` | blade axes | 16-ID-A | optics | yes |
| Attenuator | Filter | `XF:16IDB-OP{Fltr:Attn-Ax:` | attenuator | 16-ID-B | optics | yes |
| SecondarySourceAperture | Slit | `XF:16IDB-OP{Slt:SSA1` | SSA blades | 16-ID-B | optics | yes |
| HighResMirror1 | Mirror | `XF:16IDC-OP{Mir:HRM1` | HRM mirror (+ HRM2) | 16-ID-C | optics | yes |
| GuardSlit1 | Slit | `XF:16IDC-OP{Slt:G1` | guard slit (+ G2, DDA) | 16-ID-C | optics | yes |
| SAXSDetectorStage | LinearStage | `XF:16IDC-ES{Stg:SAXS` | SAXS detector positioning | 16-ID-C | detection | yes |
| WAXSDetectorStage1 | LinearStage | `XF:16IDC-ES{Stg:WAXS1` | WAXS detector 1 (+ WAXS2) | 16-ID-C | detection | yes |
| SAXSBeamStop | BeamStop | `XF:16IDC-ES{BS:SAXS` | SAXS beamstop | 16-ID-C | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:16IDC-ES{Xsp:1}` | Xspress3 | 16-ID-C | detection | yes |
| TetrAMM | FluxMonitor | `XF:16IDC-ES{TETRAMM:1}` | TetrAMM 4-channel electrometer (I0) | 16-ID-C | detection | yes |
| NSLSElectrometers | FluxMonitor (?) | `XF:16IDC-ES{NSLS_EM:1}` | NSLS-II electrometers (EM:1/2, EM:3 at IDA) | 16-ID-C | detection | yes |
| Zebra1 | TimingController (?) | `XF:16IDC-ES{Zeb:1}` | fly-scan gating | 16-ID-C | detection | yes |
| SolutionCell | LinearStage | `XF:16IDC-ES:Sol{Enc-Ax:` | solution flow cell stage (+ Sol{ctrl}) | 16-ID-C | sample | yes |
| InAirMicroscope | GenericProbe (?) | `XF:16IDC-ES:InAir{Mscp:1-Ax:` | in-air sample microscope | 16-ID-C | sample | yes |
| HPLCFlow | FlowController | `XF:16IDC-HPLC:{ES-Flow_SAXS}` | HPLC/SEC flow (+ ES-Flow_UV) | 16-ID-C | sample | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:16IDB-BI{BPM:1` | BPMs (IDB/IDC) | 16-ID-B | diagnostics | yes |
| BestMonitor | GenericProbe (?) | `XF:16IDB-CT{Best}` | BEST beam-stabilization monitor | 16-ID-B | diagnostics | yes |

Device-level prefixes read verbatim from source: `Mono:DCM`, `Mir:WBM/KBH/KBV/HRM1`, the SAXS/WAXS detector stages, `Xsp:1`, `TETRAMM:1`, the `Sol{}` solution cell, and the `HPLC:{ES-Flow_*}` delivery chain.

## Role hints

- **Positioner**: DCM, all mirrors (WBM, KB pair, HRM), slits, detector stages, solution cell.
- **Sensor**: TetrAMM (I0/flux), NSLS-II electrometers, BPMs, BEST.
- **Detector**: SAXS/WAXS area detectors (Pilatus, on the Stg:SAXS/WAXS stages), Xspress3.
- **Flow actuator**: HPLC/SEC flow + syringe pumps (startup/devices/) = FlowController.
- **Timing**: Zebra.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. The fluidic delivery (HPLC, VICI valves, pumps) runs through a mix of EPICS + vendor SDKs (the heterogeneous-delivery seam the survey notes). Aligns with `deployments/lix/`.

## New-family watch

No new coining. Confirmations:
- **HPLCFlow -> FlowController** (graduated): LIX is a named consumer in the diamond memo's rule-of-three (i22/7-bm/lix/xfp). Bind directly; LIX's HPLC pump is the canonical liquid-flow consumer.
- **TetrAMM / NSLS_EM -> FluxMonitor** (graduated): bind directly.
- **Mirrors (WBM/KB/HRM)** -> Mirror, **Xspress3** -> EnergyDispersiveSpectrometer: bind directly.
- **Zebra -> TimingController (?)**, **BPM/BEST/Microscope -> GenericProbe (loose)**: fleet-wide patterns.

## Deferred / absent

- **SAXS/WAXS area-detector** concrete PVs: the `Stg:SAXS/WAXS` stages are captured; the Pilatus camera roots are templated/in `devices/` and not isolated to a literal here (`DET-1`).
- **Fluidic delivery devices** (HPLC, syringe pumps, VICI valves in `startup/devices/`) use vendor-SDK / soft-IOC interfaces, not all `XF:` PVs; the delivery chain is the Subject/Supply/Procedure seam, captured as FlowController + notes, not fully device-mapped (`FLUID-1`).
- The **insertion-device source**: no standalone InsertionDevice instantiated in the read modules; carry `SRC-1`.
