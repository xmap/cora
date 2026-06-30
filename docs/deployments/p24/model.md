# Model

*The developer's index into where P24 content lives, its place as the chemical crystallography beamline, and the record of what is deliberately deferred. First cut.*

P24 is a descriptor-and-docs scaffold today, reverse-engineered from P24's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p24/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p24/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface; P24 adds the chemical-crystallography Practice |
| Upstream source | [P24 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p24) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P24 reuses `LinearStage` / `Slit` / `PseudoAxis` / `EnergyDispersiveSpectrometer` / `Camera` |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; chemical crystallography reuses the pending `diffraction` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P24 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P24 new

P24 is a sixteenth beamline at an existing Site, the facility's single-crystal / small-molecule chemical crystallography beamline. It is distinct from the macromolecular-crystallography beamlines (P11, i03, FMX / AMX, MANACA, TPS), which bind `Goniometer` and `mx_data_collection`: P24 does small-molecule chemical crystallography, modelled as `diffraction` for now. At the modelling level it is a reuse-and-reinforce deployment.

## No new families

P24 coins no new Family. The optics / sample banks bind `LinearStage`; the slits `Slit`; the coupled axes `PseudoAxis`; the MCA `EnergyDispersiveSpectrometer`; the area detector `Camera` (carried pending). Nothing in the catalog changes. Whether the diffractometer, once labelled, warrants a `Goniometer` / `Diffractometer` binding is carried `DIFF-1`.

## The control plane

P24 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. The handles are read from P24's public OnlineXML registry and carried confirm (`CTRL-1`); the area detector is not exposed in this slice (`DET-1`). The chemical-crystallography acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML slice exposes no undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`).** The monochromator and mirrors within the optics bank are not labelled; grouped.
- **The diffractometer geometry (`DIFF-1`).** Not labelled in the registry; grouped into the sample stage, the goniometer-vs-diffractometer binding pending.
- **The motor-bank axis roles (`GROUP-1`).** The `oh_mot*` / `mot*` banks carry no per-axis role; grouped as stage Assets.
- **The area detector (`DET-1`).** The single-crystal area detector is not in the registry slice; carried as a pending `Camera` placeholder.
- **The dummy stubs (`STUB-1`).** The `eh2_dmy*` placeholder devices are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The chemical-crystallography Method (`TECH-1`).** Whether a dedicated Method (vs reusing `diffraction`) enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p24_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
