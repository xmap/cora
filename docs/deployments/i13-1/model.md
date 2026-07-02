# Model

*The developer's by-kind index: where each CORA aggregate's I13-1 content lives, why coherent imaging coins no new family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I13-1 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes I13-1 new

I13-1 is CORA's first coherent lensless-imaging beamline. The fleet has tomography, XRF microprobe, and a hard X-ray nanoprobe (HXN), but no ptychography or coherent diffraction imaging (CDI). Ptychography raster-scans a coherent illumination across overlapping points on the sample and records a far-field coherent-diffraction pattern at each point; the real-space image is reconstructed downstream from the diffraction stack. That is the novelty, and it is an **acquisition shape plus a reconstruction**, a new Capability deferred as a pending Method (`TECH-1`), not a new device class.

## No new families

The scout that surfaced I13-1 anticipated a new "coherent imaging" device family. That is the wrong axis: coherent imaging is a Method, not a device. The devices the technique needs are a sample-scanning stage and an area detector, both of which the catalog already covers, so I13-1 coins no new Family and changes nothing in the catalog:

- **The piezo sample-scanning stage binds the catalog `LinearStage`.** The ptychography raster is its operative motion; the fixed-angle lab-frame variant (`BL13J-MO-PI-02:FIXANG:`) is a setting on the same stage, not a separate device class (`SAMPLE-1`).
- **The Merlin photon-counting detector and the side viewing camera bind the catalog `Camera`.** The Merlin records the far-field coherent-diffraction pattern (the science detector); the side camera is for alignment (`DET-1`).
- **The machine state binds the loose `StorageRing`** (`MACHINE-1`).

The coherent imaging itself is the `ptychography` Method, the fleet's first, carried pending (`TECH-1`).

## Deliberately not here yet

- **The shared I13 source and optics (`SRC-1`, `OPT-1`).** The dodal `i13_1` module exposes only the coherence-branch endstation; the undulator, monochromator, mirrors, and slits are upstream and not in the module, so they are deferred, not invented. This is the same partial-first-cut posture as I20-1.
- **The ptychography Method and the reconstruction.** Whether ptychography / CDI enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending (`TECH-1`). The image reconstruction from the diffraction stack is `ComputePort` work, not a beamline device.
- **The simulated devices and full asset-tree scenarios.** No `test_i13_1_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
