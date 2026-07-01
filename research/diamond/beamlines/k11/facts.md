# Extracted facts: K11 (DIAD)

Candidate device facts for `k11` (Diamond Light Source K11, DIAD: Dual Imaging And Diffraction). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/k11.py`, read 2026-06). Every value is carried `confirm` until K11 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! warning "Near-stub module: only KB mirror motors in public dodal"
    K11 (DIAD) combines full-field imaging and powder/single-crystal diffraction on one branch (a K-series bending-magnet beamline). The public dodal module is nearly a stub: it exposes only the two KB-mirror coordinate-system motors (X, Y). DIAD's defining instruments, the imaging camera, the diffraction detector, the sample stage, the DCM, are ABSENT from public dodal. Per the partial-scaffold discipline, those are open questions, NOT invented. dodal prefix root = **K11** (env-resolved; K-series, not the `BL##` straight-section scheme).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| KBMirrorX | Mirror | `K11-OP-KBM-01:CS:X` | Motor (KB coordinate-system X) | source | yes |
| KBMirrorY | Mirror | `K11-OP-KBM-01:CS:Y` | Motor (KB coordinate-system Y) | source | yes |

Device-level prefixes read verbatim from source: `Motor("{beamline_prefix}-OP-KBM-01:CS:X")` and `Motor("{beamline_prefix}-OP-KBM-01:CS:Y")`. The two are the X and Y coordinate-system axes of a single KB mirror system (`KBM-01`).

## Role hints

- **Positioner**: the KB mirror X/Y axes (focusing optic).

## Trust hints

dodal controls library; bluesky/GDA orchestration over devices not exposed in the public module. Trust modeled CORA-native.

## New-family watch

No new coining:
- **KB mirror motors -> Mirror** (graduated): the two axes are one KB mirror system. Bind Mirror (or model as one KB Mirror Asset with X/Y axes, matching the Asset-granularity rule, the two ACT axes are sub-detail of one KB mirror).

## Deferred / absent (most of the beamline)

DIAD's defining dual-modality instruments are absent from public dodal, all open questions:
- **IMG-1**: the full-field **imaging** camera (the "I" in DIAD).
- **DIFF-1**: the **diffraction** detector (the "D" in DIAD); when it lands, feeds the fleet-wide Diffractometer question if a diffractometer stage accompanies it.
- **MONO-1 / OPTICS-1**: DCM, the rapid imaging/diffraction beam-switching optics (DIAD's signature fast mode-switching), slits, attenuators.
- **SAMPLE-1**: the sample stage / environment.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).

This is a faithful near-stub: K11 is barely modellable from public dodal today (one KB mirror). The deployment, if built, would need staff-provided device facts. Recorded so the facility recurrence and coverage are honest about DIAD's status.
