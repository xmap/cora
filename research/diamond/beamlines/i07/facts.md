# Extracted facts: I07

Candidate device facts for `i07` (Diamond Light Source I07, surface and interface diffraction). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i07.py`, read 2026-06). Every value is carried `confirm` until I07 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! warning "Deliberately partial scaffold"
    The public i07 dodal module is THIN: it instantiates only the DCM and the insertion device. I07's defining instruments, the surface / interface **diffractometer** (a multi-circle, often 2+1 or kappa geometry for grazing-incidence surface diffraction) and its area detector, are ABSENT from the public dodal module. Per the partial-scaffold discipline (i20-1, isr precedent), those are named open questions (DIFF-1), NOT invented. dodal PVs are `{beamline_prefix}-...` with `beamline_prefix` = **BL07I** (env-resolved), insertion prefix = SR07I.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, the dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| DCM | Monochromator | motion `BL07I-MO-DCM-01:`; diagnostic `BL07I-DI-DCM-01:` | DCM (i07-specific, two PV bases) | source | yes |
| Undulator | InsertionDevice | `SR07I-MO-SERVC-01:` | InsertionDevice (i07, with harmonic-order + gap lookup) | source | yes |

Device-level prefixes read verbatim from source: `DCM("{beamline_prefix}-MO-DCM-01:", "{beamline_prefix}-DI-DCM-01:")` (the i07 DCM takes two PV bases, motion + diagnostic), `InsertionDevice("{insertion_prefix}-MO-SERVC-01:", harmonic, ...)` with a gap-calibration lookup table.

## Role hints

- **Positioner**: DCM.
- **Source**: undulator (with harmonic-order control + gap lookup table for energy selection).

## Trust hints

dodal controls library; Diamond runs bluesky/GDA over it. Trust modeled CORA-native.

## New-family watch

No new coining. Only graduated families appear:
- **DCM -> Monochromator** (graduated): note the i07 DCM uniquely takes two PV bases (motion + diagnostic); a per-beamline DCM variant, still the Monochromator family.
- **Undulator -> InsertionDevice** (catalog): with harmonic-order selection.

## Deferred / absent (the headline)

The beamline's signature instruments are absent from public dodal and are open questions, not modeled:
- **DIFF-1**: the surface / interface **diffractometer** (the multi-circle sample-orientation + detector-arm instrument that defines surface diffraction). Not in the dodal module. When it lands, it feeds the Diffractometer graduation question (the fleet-wide loose family).
- **DET-1**: the area / point detector(s) for the diffracted beam.
- **OPTICS-1**: mirrors, slits, attenuators, beam diagnostics, sample environment, all absent from the thin module.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).

This is a faithful partial: I07 is modellable only as far as dodal exposes it today (DCM + ID). The deployment, if built, would carry these two devices plus the DIFF-1/DET-1 open questions for staff.
