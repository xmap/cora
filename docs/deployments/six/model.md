# Model

*The developer's by-kind index: where each CORA aggregate's SIX content lives, the loose families this first soft X-ray deployment introduced and has since graduated, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SIX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## New loose families

SIX is CORA's first soft X-ray beamline, a new optics, detector, and sample-environment regime. It introduced three device classes no hard X-ray catalog Family covered. All three have since **graduated**: `GratingMonochromator` became a catalog Family once CSX (NSLS-II 23-ID) earned the soft X-ray PGM, `Manipulator` once ESM (NSLS-II 21-ID) earned the UHV sample manipulator, and `SpectrometerArm` once ESRF ID32 (the RIXS and XES arms) and ID28 (the multi-analyzer arm) earned the dispersive spectrometer arm SIX coined (the Monochromator, SampleManipulator, and RIXSSpectrometer here bind them).

| Family | Presents | What it is | Status |
| --- | --- | --- | --- |
| `GratingMonochromator` | Positioner | the soft X-ray plane-grating monochromator (PGM): premirror at a fixed-focus c-value plus an interchangeable grating, no Bragg crystal | graduated (SIX + CSX, `MONO-1`) |
| `SpectrometerArm` | Positioner | the meters-long energy-dispersive RIXS arm (bridge truss + optics chamber + detector chamber) | graduated (SIX + ID32 RIXS/XES + ID28) |
| `Manipulator` | Positioner | the UHV cryostat sample manipulator (x/y/z/theta) | graduated (SIX + ESM, `SAMPLE-1`) |

The catalog `Monochromator` is deliberately not stretched to cover the PGM: its note describes a crystal / multilayer Bragg monochromator, and a plane-grating mono has no Bragg crystal, selects energy by grating pitch and translation, and takes its resolution from the exit slit, so `GratingMonochromator` is a distinct Family rather than a settings variant. Likewise `SpectrometerArm` is distinct from the catalog `EnergyDispersiveSpectrometer` (a point Sensor, not a multi-chamber dispersive arm); it presents the `Positioner` Role (an arm that positions a dispersing grating and carries a `Camera` at its focus).

## Deliberately not here yet

- **The RIXS-camera Family question.** The RIXS camera does on-detector single-photon centroiding and isolinear curvature correction, a photon-counting regime distinct from an integrating-frame area detector. It is modelled here as the catalog `Camera` with that behavior carried as a note; whether the photon-counting pipeline warrants its own Family is `RIXS-2`, deferred (a `Camera`-with-settings is the lower-risk first cut).

- **The EPU polarization DOF.** The elliptically-polarizing undulator adds a phase (polarization) axis beyond gap. It binds the catalog `InsertionDevice` with the polarization carried as a setting; whether the EPU phase warrants a distinct family is deferred until a second EPU beamline (`SRC-1`).

- **The legacy end-station PGM.** The profile collection carries a discarded second monochromator instance (`Mono:2` / `espgm`) and a dead `PGMjoe` class; only the live `Mono:1` PGM is modelled.

- **The RIXS Method.** Whether RIXS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_six_*.py` registers the SIX asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
