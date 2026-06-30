# Extracted facts: B21

Candidate device facts for `b21` (Diamond Light Source B21, bio-SAXS: solution small-angle X-ray scattering with in-line SEC / HPLC sample delivery). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/b21.py`, read 2026-06). Every value is carried `confirm` until B21 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "BioSAXS with fluidic delivery"
    B21 is a solution-scattering beamline: SAXS + WAXS Eiger detectors, a fixed mirror, alignment slits, a quadrant-diode beam-intensity monitor, and a fluidic sample-delivery chain (HPLC + Vici valves + a Linkam thermal stage) for SEC-SAXS. The NSLS-II LIX precedent (solution scattering, FlowController) applies. dodal PVs are `{beamline_prefix}-...` with `beamline_prefix` = **BL21B** (env-resolved).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| SAXSDetector | Camera | `BL21B-EA-EIGER-01:` | EigerDetector | detection | yes |
| WAXSDetector | Camera | `BL21B-EA-EIGER-02:` | EigerDetector | detection | yes |
| Mirror | Mirror | `BL21B-OP-MR-01:` | SimpleMirror | optics | yes |
| Slits | Slit | `BL21B-AL-SLITS-01:` (SLITS-01/02/03/05/06/07) | Slits | optics | yes |
| IntensityMonitor | FluxMonitor (?) | `BL21B-DI-PHDGN-07:PHD1:` | QDV2F (quadrant diode) | detection | yes |
| Table | Table | `BL21B-MO-TABLE-04:` | XYStage | sample | yes |
| Panda | TimingController (?) | `BL21B-MO-PANDA-01:` | HDFPanda | detection | yes |
| Linkam | TemperatureController | `BL21B-EA-HPLC-01:` | Linkam3 | sample | yes |
| ViciValves | FlowController (?) | `BL21B-EA-GIR-01:` + `BL21B-EA-VICI-01:` | ViciValves | sample | yes |
| BeamStopCamera | Camera | `BL21B-RS-ABSB-02:CAM:` | AravisDetector | detection | yes |
| Synchrotron | GenericProbe (?) | (machine status) | Synchrotron | source | yes |

Device-level prefixes read verbatim from source: `EigerDetector(prefix="...-EA-EIGER-01:" / "-EA-EIGER-02:")`, `SimpleMirror(prefix="...-OP-MR-01:")`, the `Slits(prefix="...-AL-SLITS-NN:")` set, `QDV2F(prefix="...-DI-PHDGN-07:PHD1:")`, `HDFPanda(prefix="...-MO-PANDA-01:")`, `Linkam3(prefix="...-EA-HPLC-01:")`, `ViciValves("...-EA-GIR-01:", "...-EA-VICI-01:")`, `AravisDetector(prefix="...-RS-ABSB-02:CAM:")`.

## Role hints

- **Positioner**: mirror, slits, table.
- **Sensor**: quadrant-diode intensity monitor (I_t).
- **Detector**: two Eigers (SAXS + WAXS), the Aravis beam-stop camera.
- **Regulator**: Linkam thermal stage (sample temperature).
- **Flow**: Vici valves (sample/buffer switching in the SEC-SAXS fluidic chain).
- **Timing**: PandA (HDFPanda, fast acquisition gating).

## Trust hints

dodal controls library; bluesky/GDA orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. Reuse + a notable FlowController reinforcement:
- **EigerDetector x2 + AravisDetector -> Camera** (graduated): SAXS/WAXS + beam-stop view; bind directly.
- **Linkam3 -> TemperatureController** (graduated, presents Regulator): another consumer.
- **ViciValves -> FlowController (?)** (graduated): the SEC-SAXS valve/flow switching. FlowController is the family for flow actuators (NSLS-II lix/xfp/chx/xpd/qas consumers). Vici rotary valves are a switching-flow mechanism; confirm FlowController binding vs a dedicated valve treatment. If it binds, B21 is the first DIAMOND FlowController consumer, broadening the family cross-facility.
- **SimpleMirror -> Mirror**, **Slits -> Slit**, **XYStage -> Table** (graduated): bind directly.
- **Panda -> TimingController (?)**: the PandA gating question (fleet-wide, matches Zebra).
- **QDV2F -> FluxMonitor (?)**: a quadrant diode reads beam intensity/position; the intensity side is FluxMonitor, confirm.

## Deferred / absent

- The DCM / energy optics are not in the read module (B21 may run fixed-energy or a mono not exposed); `MONO-1`.
- The HPLC pump itself (vs the Linkam on the HPLC prefix and the Vici valves) is not a distinct device factory here; the SEC-SAXS pump is part of the fluidic seam, confirm with staff (`FLOW-1`).
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
