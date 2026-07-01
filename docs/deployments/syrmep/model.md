# Model

*The developer's index into where SYRMEP content lives, the new Elettra Site and Tango / DonkiOrchestra control house-style it introduces, the imaging spine it reuses wholesale, and the record of what is deliberately deferred. First cut.*

SYRMEP is a descriptor-and-docs scaffold today, reverse-engineered from public material: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/syrmep/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/syrmep/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; handles carried confirm-pending |
| Site descriptor | [`deployments/elettra/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/elettra/site.yaml) | the NEW Elettra facility surface; `SYRMEP` its first beamline, with the tomography Practices |
| Upstream source | [elettra.eu SYRMEP pages](https://www.elettra.eu/elettra-beamlines/syrmep.html) | the public facility material (plus the EPJ Plus 2024 review and the J. Synchrotron Rad. 2023 large-FOV paper) the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; SYRMEP reuses the imaging spine |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; core tomography Methods reused, the new ones (helical / white-beam / phase-retrieval) pending (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers SYRMEP Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes SYRMEP new

SYRMEP is two things at the facility level and nothing new at the catalog level. It is CORA's **eleventh Site** (Elettra Sincrotrone Trieste, Trieste), another re-test of the Site and Federation kernel, and the **first Tango + DonkiOrchestra** control house-style. The Tango device floor is shared with the ESRF's ID32, but the orchestration seam is the in-house, trigger-driven DonkiOrchestra framework (Elettra 2.0: the abstract "Executer" Tango device server), not BLISS and not EPICS. Its science is hard X-ray microtomography (absorption, propagation-based phase contrast, diffraction-enhanced imaging) plus the SYRMA-3D clinical breast-CT programme.

## No new families: the imaging spine ports wholesale

SYRMEP coins no new Family and changes nothing in the catalog. It is the cleanest re-test the fleet has of the imaging spine on a new Site:

- the bending-magnet source is a Supply (`PhotonBeam`), provenance only (the 2-BM precedent);
- the double-crystal Si(111) DCM binds `Monochromator`, with the mono / white (pink) beam choice as a per-Asset setting (the 2-BM `dmm_insertion` insert/retract precedent);
- the incident energy is a `PseudoAxis` over the DCM (the 2-BM energy-curve precedent);
- the laminar-beam slits bind `Slit`, the filters bind `Filter`, the upstream mask binds `Mask`;
- the heavy-payload rotation stage binds `RotaryStage` (the tomographic theta);
- the five-axis sample positioner binds `LinearStage`;
- the sample-to-detector propagation rail binds `LinearStage` (the 2-BM `CameraZ` precedent);
- the scintillator binds `Scintillator` and the sCMOS / CCD / photon-counting cameras bind `Camera`;
- the machine state binds the loose `StorageRing`.

Unlike ID32 (which bound no catalog Method), SYRMEP's core Practices bind the real catalog `tomography`, `continuous_rotation_tomography`, `mosaic_tomography`, `dark_field`, `flat_field`, and `center_alignment` Methods. The three new technique slugs (`helical_tomography`, `white_beam_tomography`, `phase_retrieval`) are registered pending in `tests/unit/deployments/test_site_descriptor.py` until they enter pilot scope.

## The Tango / DonkiOrchestra control plane

SYRMEP is the first Tango + DonkiOrchestra controls house-style in the fleet. CORA models the control handles as opaque edge strings over the `ControlPort`, the way the MX3 / ID32 heterogeneous-control precedent does. The crucial difference from ID32: **SYRMEP's handles are not in public source**. The DonkiOrchestra scan engine's source location is unconfirmed and the acquisition code is in the private `gitlab.elettra.eu` `syrmep_acquisition` group, so the handles are confirm-pending placeholders rather than read addresses (`CTRL-1`). The DonkiOrchestra orchestration (Elettra 2.0: the "Executer" device server) is the seam CORA's edge replaces, conducting over Tango rather than over BLISS or EPICS.

## Deliberately not here yet

| Deferred | Why | Tracking |
| --- | --- | --- |
| Every concrete control handle | not in public source (private gitlab group, unconfirmed DonkiOrchestra source) | `CTRL-1` |
| PSS permit signals and shutters | not in public source, not invented | `PSS-1` |
| The default routine camera, pixel size, FOV | sources name multiple detectors without pinning the routine one | `DET-1` |
| Helical CT, white-beam tomography, phase retrieval as catalog Methods | a CORA-scope decision pending pilot scope | `TECH-1` |
| The reconstruction pipeline as Compute provenance | post-acquisition compute; modelled when the deployment firms up | `COMPUTE-1` |
| Scenarios, operations runbook, live experiment view | SYRMEP is not yet driven by CORA | follows the [2-BM](../2-bm/index.md) shape |
