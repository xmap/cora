# Model

*The developer's index into where SIX content lives, the new loose families this first soft X-ray deployment introduces, and the record of what is deliberately deferred. First cut.*

SIX is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's profile collection: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/six/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/six/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `SIX` added to its beamline list, with a RIXS Practice |
| Extraction provenance | [NSLS2/six-profile-collection](https://github.com/NSLS2/six-profile-collection) | the `startup/*.py` device classes the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; three new device classes stay loose at n=1 (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the RIXS Method is not yet coined (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers SIX Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## New loose families

SIX is CORA's first soft X-ray beamline, a new optics, detector, and sample-environment regime. It introduces three device classes no existing catalog Family covers. Per earn-the-abstraction, each is held **loose at n=1** and graduates nothing: a second independent soft X-ray beamline must earn the abstraction before any catalog change. Their names are provisional, to be settled by the naming-r3 gate at graduation.

| Loose family | Presents (when graduated) | What it is | Earns when |
| --- | --- | --- | --- |
| `GratingMonochromator` | Positioner | the soft X-ray plane-grating monochromator (PGM): premirror at a fixed-focus c-value plus an interchangeable grating, no Bragg crystal | a 2nd PGM beamline (NSLS-II CSX / ESM / SST) (`MONO-1`) |
| `SpectrometerArm` | confirm (Sensor or Positioner) | the meters-long energy-dispersive RIXS arm (bridge truss + optics chamber + detector chamber) | a 2nd RIXS / dispersive-arm beamline (`RIXS-1`) |
| `Manipulator` | Positioner | the UHV cryostat sample manipulator (x/y/z/theta) | a 2nd UHV-manipulator soft beamline (`SAMPLE-1`) |

The catalog `Monochromator` is deliberately not stretched to cover the PGM: its note describes a crystal / multilayer Bragg monochromator, and a plane-grating mono has no Bragg crystal, selects energy by grating pitch and translation, and takes its resolution from the exit slit. Whether `GratingMonochromator` graduates as its own Family or the catalog `Monochromator` is generalized is a gate-review / naming-r3 decision at the 2nd sighting, not this PR's. Likewise `SpectrometerArm` is distinct from the catalog `EnergyDispersiveSpectrometer` (a point Sensor, not a multi-chamber dispersive arm).

## Deliberately not here yet

- **The RIXS-camera Family question.** The RIXS camera does on-detector single-photon centroiding and isolinear curvature correction, a photon-counting regime distinct from an integrating-frame area detector. It is modelled here as the catalog `Camera` with that behavior carried as a note; whether the photon-counting pipeline warrants its own Family is `RIXS-2`, deferred (a `Camera`-with-settings is the lower-risk first cut).

- **The EPU polarization DOF.** The elliptically-polarizing undulator adds a phase (polarization) axis beyond gap. It binds the catalog `InsertionDevice` with the polarization carried as a setting; whether the EPU phase warrants a distinct family is deferred until a second EPU beamline (`SRC-1`).

- **The legacy end-station PGM.** The profile collection carries a discarded second monochromator instance (`Mono:2` / `espgm`) and a dead `PGMjoe` class; only the live `Mono:1` PGM is modelled.

- **The RIXS Method.** Whether RIXS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_six_*.py` registers the SIX asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
