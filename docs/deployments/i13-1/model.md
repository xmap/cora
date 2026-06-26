# Model

*The developer's index into where I13-1 content lives, why coherent imaging coins no new family, and the record of what is deliberately deferred. First cut, deliberately partial.*

I13-1 is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's dodal device layer: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i13-1/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i13-1/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; `I13-1` added to its beamline list, with a ptychography Practice |
| Extraction provenance | [DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal) | the `src/dodal/beamlines/i13_1.py` factory the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the ptychography Method is pending (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers I13-1 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

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

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
