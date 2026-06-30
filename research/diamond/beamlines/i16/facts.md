# Extracted facts: I16

Candidate device facts for `i16` (Diamond Light Source I16, materials and magnetism: resonant and non-resonant X-ray scattering on a multi-circle diffractometer). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i16.py`, read 2026-06). Every value is carried `confirm` until I16 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! warning "Deliberately partial scaffold"
    The public i16 dodal module is THIN: it instantiates only the undulator (with harmonic order) and two Lakeshore sample-temperature controllers. I16's defining instrument, the **six-circle (kappa) diffractometer** that is the heart of its resonant-scattering and magnetism program, plus the DCM, mirrors, and detectors, are ABSENT from the public module. Per the partial-scaffold discipline (i07/i20-1/isr precedent), those are named open questions (DIFF-1), NOT invented. dodal PVs are `{beamline_prefix}-...` with `beamline_prefix` = **BL16I** (env-resolved), insertion prefix = SR16I.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| Undulator | InsertionDevice | `SR16I-MO-SERVC-01:` | UndulatorInMm (+ UndulatorOrder harmonic) | source | yes |
| SampleTemperatureController336 | TemperatureController | `BL16I-EA-LS336-01:` | Lakeshore336 | sample | yes |
| SampleTemperatureController340 | TemperatureController | `BL16I-EA-LS340-01:` | Lakeshore340 | sample | yes |

Device-level prefixes read verbatim from source: `UndulatorInMm(prefix="{insertion_prefix}-MO-SERVC-01:")`, `Lakeshore336(prefix="{beamline_prefix}-EA-LS336-01:")`, `Lakeshore340(prefix="{beamline_prefix}-EA-LS340-01:")`.

## Role hints

- **Source**: undulator with harmonic-order selection.
- **Regulator**: two Lakeshore temperature controllers (LS336 + LS340), settable-setpoint thermal actuators for the low-temperature magnetism program. Note the two distinct Lakeshore models on one beamline.

## Trust hints

dodal controls library; bluesky/GDA orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. Only graduated families appear:
- **Lakeshore336 + Lakeshore340 -> TemperatureController** (graduated, presents Regulator): i16 is another consumer, and it broadens the mechanism range (a second Lakeshore model). Bind both directly.
- **Undulator -> InsertionDevice** (catalog): bind directly.

## Deferred / absent (the headline)

I16's defining instruments are absent from public dodal, named as open questions:
- **DIFF-1**: the **six-circle / kappa diffractometer** (the multi-circle sample-orientation + detector-arm instrument central to resonant magnetic scattering). When it lands, it feeds the fleet-wide Diffractometer graduation question, and i16's is likely a genuine full multi-circle (a strong vote toward graduating the true-diffractometer subset, distinct from the 2-axis stubs).
- **MONO-1 / OPTICS-1**: DCM, mirrors, slits, attenuators, all absent.
- **DET-1**: area / point detectors (Pilatus / APD for resonant scattering), absent.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).

This is a faithful partial: i16 is modellable only as far as dodal exposes it today (undulator + two Lakeshores). The deployment, if built, would carry these plus the DIFF-1/DET-1 open questions.
