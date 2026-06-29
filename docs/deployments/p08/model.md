# Model

*The developer's index into where P08 content lives, its place as the high-resolution diffraction beamline, and the record of what is deliberately deferred. First cut.*

P08 is a descriptor-and-docs scaffold today, reverse-engineered from P08's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p08/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p08/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface; P08 adds the diffraction Practice |
| Upstream source | [P08 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P08 reuses the optics / motion / detector Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; diffraction reuses the pending `diffraction` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P08 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P08 new

P08 is a twelfth beamline at an existing Site, the facility's high-resolution diffraction beamline (surface / interface diffraction, reflectivity, high-resolution powder / single-crystal). At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level, distinguished mainly by its rich detector set.

## No new families

P08 coins no new Family. The DCM and multilayer mono bind `Monochromator`; the CRL `Transfocator`; the absorber `Filter`; the six-circle Kohzu diffractometer `Goniometer`; the hexapod `Hexapod`; the slits `Slit`; the detectors `Camera` / `EnergyDispersiveSpectrometer`. Nothing in the catalog changes. The Mythen2 strip detector is modelled as a `Camera` for now (a fold-vs-promote question for the catalog owner, the P10 precedent).

## The control plane

P08 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the Kohzu six-circle diffractometer controller and the breadth of detectors (Eiger / Pilatus / Mythen / PerkinElmer / Vortex). The handles are read from P08's public OnlineXML registry and carried confirm (`CTRL-1`). The high-resolution diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The gap is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The DCM / multilayer crystal cut and the CRL detail are carried confirm-pending.
- **The diffractometer structure (`DIFF-1`, `GROUP-1`).** The six-circle Kohzu geometry and the per-axis `diff*` bank roles are pending; modelled as a `Goniometer` Asset.
- **The sample hexapod geometry (`SAMPLE-1`).** Carried confirm-pending.
- **The detector roster (`DET-1`).** The models, the operative roster, and the Mythen fold-vs-promote are named, not fully bound.
- **The shared Lambda host (`HOST-1`).** A Lambda reports on the bare `petra3` host.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p08_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
