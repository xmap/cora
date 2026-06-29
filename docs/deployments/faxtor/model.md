# Model

*The developer's index into where FAXTOR content lives, the new ALBA Site and Tango / Sardana control house-style it introduces, and the record of what is deliberately deferred. First cut.*

FAXTOR is a descriptor-and-docs scaffold today, reverse-engineered from ALBA's public facility pages: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/faxtor/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/faxtor/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; control handles unbound (`CTRL-1`) |
| Site descriptor | [`deployments/alba/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/alba/site.yaml) | the NEW ALBA facility surface; `FAXTOR` its first beamline, with the tomography Practices |
| Research provenance | [`research/alba/_research_brief.md`](https://github.com/xmap/cora/blob/main/research/alba/_research_brief.md) | the verified online research brief the descriptor and docs were curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; FAXTOR reuses the imaging Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; tomography reuses existing Methods, radiography is pending (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers FAXTOR Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes FAXTOR new

FAXTOR is two things at the Site level and nothing new at the vocabulary level. It is CORA's **eighth Site** (ALBA, Barcelona), a re-test of the Site and Federation kernel, and the **second Tango / Sardana / Taurus** control plane CORA models. ALBA is the originating institution of Sardana (and of the Taurus GUI framework and the IcePAP motion controller), so this is the controls house-style's home facility; MAX IV (TomoWISE) was the first consumer CORA modelled. Its science is fast X-ray tomography and radiography on a multipole-wiggler source.

## No new families (the imaging spine reuses the 2-BM / TomoWISE precedent)

FAXTOR coins no new Family. The multipole wiggler binds the catalog `InsertionDevice`; the double multilayer monochromator binds `Monochromator`; the filters bind `Filter` and the slits bind `Slit`; the focusing mirrors bind `Mirror` (deferred, `OPT-1`); the experiment endstation binds `Table`, `RotaryStage`, `LinearStage`, and `Shutter`; the detector binds `Scintillator` and `Camera`; the machine state binds the loose `StorageRing`. Nothing in the catalog changes.

## The Tango / Sardana control plane

FAXTOR is the second Tango / Sardana / Taurus controls house-style in the fleet, after MAX IV TomoWISE. Device IO is a layer of Tango device servers (motors over IcePAP-class controllers, detectors via the Lima framework); Sardana provides the experiment-orchestration layer (a Pool of controllers / motors / measurement groups, plus a MacroServer running scan macros), and Taurus is the operator UI. ALBA publishes no per-beamline device manifest, so CORA does not bind the Tango / Sardana / IcePAP handles here; when bound they would be modelled as opaque edge strings over the `ControlPort`, the way the MX3 and ID32 heterogeneous-control precedents do (`CTRL-1`). The fast continuous-rotation tomography acquisition runs through Sardana macros; that orchestration is the seam CORA's edge replaces, conducting over Tango / IcePAP rather than replacing Sardana. The Lima detector file-writing to the ALBA data store is plumbing CORA observes, not data it owns.

## Deliberately not here yet

- **The control handles (`CTRL-1`).** No public per-beamline Tango / Sardana / IcePAP manifest exists; the handles are carried pending, not invented.
- **The detector model (`DET-1`).** The fast camera and scintillator are bound to `Camera` and `Scintillator` but their models are unpublished, carried fully pending.
- **The exact optics detail (`MONO-1`, `FILT-1`, `OPT-1`, `OPT-2`).** The DMM coating and energy partition, the filter set, the mirrors, and the slit blade map are carried confirm-pending.
- **The endstation stage stack (`SAMPLE-1`, `TRIG-1`).** The rotary, positioning, table, and shutter are named; their axis sets, models, and the trigger scheme are pending.
- **Radiography as a Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the 7-BM `radiography` slug. Fast tomography reuses the catalog Methods directly.
- **The simulated devices and full asset-tree scenarios.** No `test_faxtor_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
