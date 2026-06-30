# Model

*The developer's index into where P23 content lives, its place as a thin in-situ diffraction scaffold, and the record of what is deliberately deferred. First cut.*

P23 is a descriptor-and-docs scaffold today, reverse-engineered from P23's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p23/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p23/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface; P23 adds the diffraction Practice |
| Upstream source | [P23 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P23 reuses `LinearStage` / `Camera` |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; in-situ diffraction reuses the pending `diffraction` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P23 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P23 new

P23 is a fifteenth beamline at an existing Site, the facility's in-situ / operando diffraction beamline. At the modelling level it is a reuse-and-reinforce deployment, and a deliberately thin one given its sparse registry slice (one generic motor bank).

## No new families (a thin, honest model)

P23 coins no new Family. The motor bank binds `LinearStage`; the detectors are a pending `Camera` placeholder. Nothing in the catalog changes. The P23 registry slice exposes little beyond the grouped motor bank, so the optics / diffractometer breakdown and the detectors are carried grouped / pending rather than invented (`OPT-1`, `DIFF-1`, `DET-1`), the same model-what-the-source-supports posture as P11 / P21 / P65.

## The control plane

P23 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. The handles are read from P23's public OnlineXML registry and carried confirm (`CTRL-1`). The in-situ diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML slice exposes no undulator device; the source is carried pending.
- **The optics / diffractometer breakdown (`OPT-1`, `DIFF-1`).** The mono, mirrors, and diffractometer within the bank are not labelled; grouped.
- **The motor-bank axis roles (`GROUP-1`).** The `eh_mot*` bank carries no per-axis role; grouped as one stage.
- **The dev stub (`STUB-1`).** The single `hasep23dev` axis is a dev / commissioning device, noted.
- **The detectors (`DET-1`).** Not in the registry slice; carried as a pending `Camera` placeholder.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p23_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
