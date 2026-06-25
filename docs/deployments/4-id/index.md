# 4-ID POLAR

*Polarization and magnetic-scattering beamline at APS. This page walks the operational core CORA models today across four stations. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `4-ID POLAR` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 4` (organizational grouping; not a registered Asset) |
| Status | First cut, reverse-engineered (operational core modelled; Raman station and the diffractometer Assembly deferred) |
| Sources | Undulator pair on the S04ID straight section |
| Control stack | APS EPICS (the same floor as 2-BM); device handles bound from the beamline's instrument repo, carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/polar-bits](https://github.com/BCDA-APS/polar-bits)); the extraction is in [`research/aps-reverse-engineering/`](https://github.com/xmap/cora/tree/main/research/aps-reverse-engineering). Unlike the 7-BM and 32-ID design-phase scaffolds, it binds the real EPICS control handles, because POLAR is operational. Every value is still carried as `confirm` until 4-ID staff verify it: a PV read from the operator's config is strong evidence, not a CORA-owned fact. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes 4-ID different

4-ID POLAR is CORA's first non-tomography APS deployment. It is unlike the 2-BM, 7-BM, and 32-ID imaging beamlines in three ways:

- **Polarization control.** Three diamond phase retarders set the X-ray polarization state, the capability POLAR is built around. CORA has no phase-retarder Family yet (a loose `PhaseRetarder`).
- **Magnetic scattering.** Superconducting sample magnets (2 T at 4-ID-B, a high-field magnet at 4-ID-H) and low-temperature sample environments drive resonant magnetic scattering. New device classes to CORA: `Magnet` (loose) and `TemperatureController` (since graduated to a catalog Family presenting `Regulator`).
- **Diffraction.** Huber diffractometers at 4-ID-G replace the tomography stage with a multi-circle goniometer and reciprocal-space (hklpy2) coordination, a shape CORA models as an Assembly, not yet built.

It runs across four lead-shielded stations: `4-ID-A` (optics), and `4-ID-B`, `4-ID-G`, `4-ID-H` (experiment).

## Scope: what is and is not modelled

This cut earns its abstractions. It models the operational core read from the beamline config and defers the rest.

| Part | In this cut | Why |
| --- | --- | --- |
| Optics spine (`4-ID-A`) | Yes | Undulators, phase retarders, VDCM monochromator, white-beam and mono slits |
| Per-station optics (`4-ID-B/G/H`) | Yes | KB mirrors, filters, transfocator, beam-position monitors |
| Diffractometers (`4-ID-G`) | Yes, as plain devices | Modelled with their circle axis maps; the reusable `Assembly(Diffractometer)` is designed but deferred (`DIFF-1`, see [Model](model.md#deliberately-not-here-yet)) |
| Sample environment | Yes | Magnets, temperature controllers, sample tables, pump-probe laser, bound to loose Families |
| Raman station (`4-ID-Raman`) | No | Its device config did not extract (a broken symlink in the source clone); scope and devices are `TOPO-2` |
| Preamps / lock-in / high-pressure cell | No | Present in the config; deferred as peripheral (`SAMPLE-2`) |

The deferred parts and the reasons are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

The systems CORA models today, along the beam:

- [Source](beamline.md): the generated device walk, rendered from the descriptor: the undulator source, the phase retarders, the VDCM monochromator and its slits, the diamond window, toroidal and high-heat-load mirrors, the transfocator, and the per-station KB mirrors and filters.
- [Sample](equipment/sample.md): the 4-ID-G diffractometers, the polarization analyzer, and the magnet / temperature / table sample environment across the stations.
- [Detector](equipment/detector.md): the Eiger area detector, flag-view cameras, beam-position monitors, and scaler counters.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS control stack; the device handles are bound from the beamline config and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id`, with Families and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/4-id/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 4-ID is designed to do, as intent. Each is a portable [Catalog](../../catalog/methods.md) Method that an APS [Practice](../aps/index.md#the-techniques-adapted-here) would adapt. POLAR's techniques (diffraction, magnetic scattering, dichroism) are new to CORA's imaging-heritage catalog and render unlinked, carried pending.

## Governance

[Governance](governance.md): who will act at 4-ID and the trust shape that gates their commands. People and agents are facility principals at the [APS Site](../aps/index.md#who-acts-here).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's 4-ID content lives, the loose-Family graduation plan, and the record of what is deliberately deferred (the diffractometer Assembly, the Raman station, scenarios, Models).

## Not yet documented

4-ID is not yet driven by CORA, so the operations runbook (procedures, recipes, cautions, enclosure permits) and the live experiment view are deliberately not written yet: a runbook for a beamline CORA does not yet drive would be invention, not record. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
