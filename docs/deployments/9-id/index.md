# 9-ID

*The Coherent Surface Scattering Instrument (CSSI) at APS. This page walks the operational core CORA models today across two stations. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `9-ID` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 9` (organizational grouping; not a registered Asset) |
| Status | First cut, reverse-engineered (operational core modelled; the metadata / Data Management seam and the simulated devices deferred) |
| Source | A planar undulator on the S09ID straight section |
| Control stack | APS EPICS (the same floor as 2-BM); device handles bound from the beamline's instrument repo, carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/9id_bits](https://github.com/BCDA-APS/9id_bits)); the extraction is in [`research/aps-reverse-engineering/`](https://github.com/xmap/cora/tree/main/research/aps-reverse-engineering). Like 4-ID and 8-ID it binds the real EPICS control handles, because 9-ID is operational. Every value is carried as `confirm` until 9-ID staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes 9-ID different

9-ID is a coherent-scattering beamline whose signature is **grazing incidence**: the sample sits at a shallow angle to a coherent beam so the measurement is surface-sensitive (GISAXS, GIWAXS, and surface XPCS).

- **A surface-scattering sample geometry.** The CSSI sample stack pairs a translation stage with an incidence rotation that sets the shallow angle. That grazing-incidence shape is new to CORA's imaging-heritage and diffraction deployments.
- **Almost pure catalog reuse.** Every optic and detector binds a Family CORA already has (`InsertionDevice`, `Monochromator`, `Mirror`, `Aperture`, `Filter`, `Slit`, `Hexapod`, `Camera`, `BeamStop`). 9-ID adds **no new catalog Family**, so it is evidence the catalog holds for a beamline outside the imaging core.
- **A clean system-of-record seam.** The instrument config carries a large set of metadata PVs and an APS Data Management workflow trigger. Those are the experiment-record bookkeeping CORA's own system of record replaces, so they are a seam, deliberately not modelled as Assets (see [Model](model.md#the-metadata-and-data-management-seam)).

It runs across two stations: `9-ID-A` (optics) and `9-ID-D` (the CSSI endstation: focusing, the grazing-incidence sample, and the detectors).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`9-ID-A`) | Yes | Undulator, Kohzu monochromator, FMBO mirrors, white-beam apertures, attenuator |
| Focusing + guard slits (`9-ID-D`) | Yes | CRL transfocator, KB mirror, three guard slits |
| CSSI sample (`9-ID-D`) | Yes | Grazing-incidence stage, incidence rotation, alignment hexapods, viewing microscope |
| Detectors (`9-ID-D`) | Yes | Pilatus, Eiger on a stage, WAXS detector, beam stop, beam-position monitors |
| Metadata / Data Management PVs | No | The experiment-record bookkeeping CORA's system of record replaces (a seam, not Assets) |
| Diagnostic flags + DAMM mask | Coarsely | Carried only insertion-motor PVs; folded into a note pending identification (`DIAG-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

- [Source](beamline.md): the generated device walk: the undulator, the Kohzu monochromator, the FMBO mirrors, the white-beam apertures and attenuator, and the 9-ID-D focusing (CRL transfocator, KB mirror) and guard slits.
- [Sample](equipment/sample.md): the grazing-incidence CSSI sample stack (translation, incidence rotation, alignment hexapods, viewing microscope).
- [Detector](equipment/detector.md): the coherent area detectors, the WAXS detector, the beam stop, and the beam-position monitors.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS control stack and the metadata / Data Management seam; handles bound from the beamline config and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/9-id/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 9-ID is designed to do, as intent. Surface XPCS shares 8-ID's now-catalog `xpcs` Method; coherent surface scattering and grazing-incidence scattering are still new to CORA's imaging-heritage catalog and render unlinked, carried pending.

## Governance

[Governance](governance.md): who will act at 9-ID and the trust shape that gates their commands. People and agents are facility principals at the [APS Site](../aps/index.md#who-acts-here).

## Model

[Model](model.md): the developer's by-kind index, the catalog reuse this deployment proves, the metadata seam, and the record of what is deliberately deferred.

## Not yet documented

9-ID is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
