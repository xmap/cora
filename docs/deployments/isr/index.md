# ISR

*The In Situ and Resonant beamline at NSLS-II, beamline 4-ID: hard X-ray resonant elastic / inelastic scattering near absorption edges, surface and interface diffraction (crystal truncation rods), and in-situ sample environments. This page walks the operational core CORA models today. It is a reverse-engineered, and deliberately partial, first cut: the public source is an early, optics-first profile collection.*

| Property | Value |
| --- | --- |
| Asset | `ISR` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 4` (PV namespace `XF:04ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase, **partial** (optics + detector + two end-station axes; the diffractometer is deferred) |
| Source | An in-vacuum undulator (read-only gap in source) (`SRC-1`) |
| Control stack | NSLS-II EPICS / ophyd, bluesky-queueserver + Tiled; handles bound from the profile collection, carried confirm (`CTRL-1`) |

!!! warning "First cut, partial, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/isr-profile-collection](https://github.com/NSLS2/isr-profile-collection)), which is an **early / commissioning, optics-and-detectors-first** scaffold. EPICS PVs are real and read from the `startup/` files; the devices that ISR's name implies (the multi-circle diffractometer, the in-situ sample environment, a wired resonant energy axis, polarization analysis) are **absent or stubbed** in the source and are carried as open questions, not invented. Every modelled value is carried as `confirm` until ISR staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What ISR is, and what the source actually contains

ISR's mission is hard X-ray **in-situ** and **resonant** studies: resonant scattering near absorption edges, surface and interface diffraction (crystal truncation rods), and in-situ environments (electrochemistry, gas, temperature). That mission needs a multi-circle diffractometer, a tunable resonant energy axis, in-situ sample cells, and often polarization analysis.

The honest finding, and the reason this is a partial cut, is that the **public profile collection does not yet contain those mission devices.** What it binds is an optics-and-detectors-first scaffold:

- the front-end slit, the in-vacuum undulator gap (read-only), the double-crystal monochromator, the bendable focusing mirror pair, and the harmonic-rejection mirror;
- the four-foil attenuator bank;
- the Eiger 1M area detector and the diagnostic screen cameras;
- and, of the diffractometer, **only two bound axes** (a sample rotation `th` and a second axis `zeta`, under the `Dif:ISD` diffractometer IOC).

The multi-circle diffractometer (its orientation circles, its detector two-theta arm, its reciprocal-space engine), the in-situ sample environment, a wired resonant energy axis, and polarization analysis are all **absent or stubbed** (the flux-monitor electrometers are even commented out, and the energy axis is a non-functional stub). So CORA models what is PV-bound and routes the four mission-critical gaps to [Open questions](questions.md), the same discipline the [i20-1](../i20-1/index.md) (EDE) partial follows.

ISR coins **no new Family** and changes nothing in the catalog. Its science would reuse the existing pending `resonant_scattering` Method (APS [4-ID](../4-id/index.md), [CSX](../csx/index.md)) and `diffraction` Method (4-ID / [8-ID](../8-id/index.md)); both are deferred, and doubly so here because the diffractometer they run on is not yet in source.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`FE:C04A`, `XF:04IDA-OP`, `XF:04IDB-OP`) | Yes | The undulator gap, the DCM, the focusing pair, the harmonic-rejection mirror, the front-end slit (`ENC-1`) |
| Endstation (`XF:04IDD-ES`) | Yes (partial) | The filter bank, the two bound sample axes (`th`, `zeta`), the Eiger 1M (`ENC-1`) |
| New device classes | None | Zero new Families coined; nothing graduates; the catalog is unchanged |
| The multi-circle diffractometer | No (absent in source) | Only `th` + `zeta` are bound; the orientation circles, detector arm, and reciprocal-space engine are an open question (`DIFF-1`) |
| The in-situ sample environment | No (absent in source) | No temperature / electrochemistry / gas / cryostat device is PV-bound (`INSITU-1`) |
| The resonant energy axis + polarization | No (stubbed / absent) | The energy axis is a non-functional stub; no polarization analyzer or phase retarder is bound (`RESONANT-1`) |
| The flux monitors | No (commented out) | The QuadEM electrometers are defined but commented out in source (`DET-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **ISR is a deliberately partial scaffold.** CORA models the PV-bound optics + Eiger + the two bound end-station axes, and routes the absent mission devices (diffractometer, in-situ environment, resonant energy axis, polarization) to open questions rather than inventing them (`DIFF-1`, `INSITU-1`, `RESONANT-1`).
- **The single bound sample rotation binds `RotaryStage`, not `Goniometer`.** Only `th` + `zeta` are bound under the `Dif:ISD` IOC; with no detector arm and no reciprocal-space engine there is no basis to scaffold a multi-circle `Goniometer`, so it is one `RotaryStage` Asset with the full diffractometer deferred (`DIFF-1`).
- **4-ID is an undulator beamline.** The in-vacuum undulator is observed (read-only gap in source) alongside the loose `StorageRing`; the device detail is `SRC-1`.
- **The optics reuse the catalog.** The DCM binds `Monochromator`; the bendable focusing pair and the harmonic-rejection mirror bind `Mirror`; the front-end slit binds `Slit`; the filter bank binds `Filter`.
- **The Eiger and screen cameras bind `Camera`; the motorized BPM stage binds the loose `BeamPositionMonitor`.** The flux-monitor electrometers are commented out in source, so no `FluxMonitor` Asset is modelled (`DET-1`, `DIAG-1`).
- **Zero new Families coined, no new Method slugs, nothing graduates, the catalog is unchanged.**

## The beamline

- [Source](beamline.md): the generated device walk: the storage-ring machine state, the in-vacuum undulator gap, the double-crystal monochromator, the bendable focusing pair and the harmonic-rejection mirror, the front-end slit, and the attenuator bank.
- [Sample](equipment/sample.md): the two bound end-station axes (`th` / `zeta`), and where the absent multi-circle diffractometer and in-situ environment sit.
- [Detector](equipment/detector.md): the Eiger 1M area detector, the diagnostic screen cameras, the motorized beam-position monitor, and the commented-out flux monitors.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack, the early-commissioning signals, and the absent mission devices; handles bound from the profile collection and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/isr/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what ISR is designed to do, as intent. Resonant scattering maps to the pending `resonant_scattering` Method (shares 4-ID / CSX) and surface / CTR diffraction to the pending `diffraction` Method (shares 4-ID / 8-ID). Both render unlinked and are doubly deferred: the Methods are pending and the diffractometer they run on is absent from source (`TECH-1`, `DIFF-1`).

## Governance

[Governance](governance.md): who will act at ISR and the trust shape that gates their commands. People and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), surfacing through their actions and gated by a Zone-plus-Conduit-plus-Policy trust shape. The NSLS-II operator pool and review are pending at the Site (`GOV-1`). No PSS / photon-shutter / hutch-interlock device is in the profile collection, so the permit signals are carried pending, not invented (`PSS-1`).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's ISR content lives, and the record of what is deliberately deferred. ISR introduces no new Family.

## Not yet documented

ISR is not yet driven by CORA, and its source is an early partial, so the operations runbook and the live experiment view are deliberately not written yet. They join as the diffractometer and in-situ environment enter the source and the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and the absent mission devices are not invented here (`PSS-1`, `DIFF-1`, `INSITU-1`, `RESONANT-1`).
