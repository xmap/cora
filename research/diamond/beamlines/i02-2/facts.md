# Extracted facts: I02-2 (VMXi)

Candidate device facts for `i02-2` (Diamond Light Source I02-2, also known as VMXi / I02I: versatile macromolecular crystallography, in-situ plate screening). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i02_2.py`, read 2026-06). Every value is carried `confirm` until VMXi staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! warning "Near-stub module: only a sample stage in public dodal"
    The public i02-2 dodal module is nearly a stub: it exposes the shared `Synchrotron` status device and a single sample XY stage. VMXi's defining instruments, the in-situ crystallisation-plate handling, the imaging/screening detector, the DCM and optics, are ABSENT from public dodal. Per the partial-scaffold discipline, those are open questions, NOT invented. dodal prefix root = **BL02I** (env-resolved via `BeamlinePrefix(BL, suffix="I")`).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| SampleStage | LinearStage | `BL02I-MO-GONIO-01:SAMPLE:` | XYStage | sample | yes |
| Synchrotron | GenericProbe (?) | (machine status, no beamline PV) | Synchrotron | source | yes |

Device-level prefix read verbatim from source: `XYStage("{beamline_prefix}-MO-GONIO-01:SAMPLE:")`.

## Role hints

- **Positioner**: the sample XY stage (plate positioning for in-situ screening).

## Trust hints

dodal controls library; bluesky/GDA orchestration over devices not exposed in the public module. Trust modeled CORA-native.

## New-family watch

No new coining, almost nothing to assess:
- **XYStage -> LinearStage** (graduated): the sample plate-positioning stage. Note the `MO-GONIO-01:SAMPLE:` PV path (a gonio namespace), but the class is a plain XY stage; bind LinearStage. (VMXi screens plates rather than rotating single crystals, so a full goniometer is not expected here.)

## Deferred / absent (most of the beamline)

VMXi's defining instruments are absent from public dodal, all open questions:
- **PLATE-1**: the in-situ crystallisation-**plate handling** system (the robotic plate loader / hotel that is VMXi's whole point).
- **DET-1**: the imaging / screening detector.
- **MONO-1 / OPTICS-1**: DCM, mirrors, slits, attenuators.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).

This is a faithful near-stub: VMXi is barely modellable from public dodal today (one sample stage). The deployment, if built, would need staff-provided device facts. Recorded so the facility recurrence and coverage are honest about VMXi's status.
