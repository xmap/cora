# Sample

*The endstation sample side: the two bound axes of the diffractometer, and the absent multi-circle diffractometer and in-situ environment. A deliberately partial first cut; PVs read from the `NSLS2/isr-profile-collection` startup files, carried confirm.*

This page is where ISR's partial source shows most plainly. ISR's science, resonant scattering and surface / interface diffraction (crystal truncation rods), needs a multi-circle diffractometer: sample-orientation circles, a detector two-theta arm, and a reciprocal-space (hkl) engine. The public profile collection does not yet contain it. What it binds is two axes.

## The sample side at a glance

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleStage` | `RotaryStage` | `XF:04IDD-ES:1{Dif:ISD-Ax:th}` | the two bound axes of the `Dif:ISD` diffractometer: a sample rotation (`th`, the operative scan axis) and a second axis (`zeta`) (`DIFF-1`) |

## What is bound, and what is not

The endstation IOC `Dif:ISD` ("Diffractometer, In-Situ Diffraction") binds exactly two axes in the profile collection: a sample rotation `th` and a second axis `zeta` (its rotary-versus-linear nature is not determinable from source). The beamline's plans confirm the minimal reality: the default scan is a one-dimensional rocking scan of `th`, and the attenuated scans step `zeta`. CORA models these as a single `RotaryStage` Asset (`th` is the operative rotation; `zeta` is carried as a second axis on the same Asset).

The IOC name (`Dif:ISD`) shows a diffractometer exists on the floor, but the source binds only these two of its axes. With **no detector two-theta arm, no orientation circles (chi / phi / mu / eta / delta / gamma / nu), no sample translations, and no reciprocal-space engine** in the source, there is no basis to scaffold a multi-circle `Goniometer`. So CORA carries one `RotaryStage` and routes the full diffractometer to an open question (`DIFF-1`), the same discipline the [i20-1](../../i20-1/index.md) (EDE) partial uses for its absent dispersive optics.

## The in-situ environment is absent

ISR's name promises in-situ studies (electrochemistry, gas, temperature, cryostat). The profile collection binds **none** of it: there is no temperature controller, no potentiostat / electrochemistry, no gas / flow controller, and no cryostat anywhere in the source. The in-situ sample environment is a stated mission with zero device representation in the public source, so it is a named open question, not modelled (`INSITU-1`). When it lands, the environments would reuse existing families and the seam (a `TemperatureController` for thermal, the graduated `FlowController` for gas / flow, the LIX / XFP precedent), with the sample itself a Subject; none is invented here.

## Resonant and polarization, deferred

Resonant scattering needs a tunable energy axis near absorption edges, and often polarization analysis. The DCM Bragg (see [Source](../beamline.md)) is the physical energy axis, but a wired energy pseudo-axis is only a non-functional stub in source, and no polarization analyzer or phase retarder is bound. So the resonant energy axis and polarization analysis are carried as an open question, not modelled (`RESONANT-1`). When wired, the energy axis would be a `PseudoAxis` over the DCM (the 2-BM beam-energy precedent) and any polarization hardware would reuse the loose `PolarizationAnalyzer` / `PhaseRetarder` families that APS 4-ID POLAR holds.

## Why no new Family here

The one bound sample device reuses the catalog `RotaryStage`. CORA deliberately does not scaffold a `Goniometer`, an in-situ environment, or a resonant axis that the source does not contain; those are named open questions. Nothing here graduates and the catalog is unchanged.

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the partial-scaffold rationale, and [the source walk](../beamline.md) for the PVs as read from the profile collection.
