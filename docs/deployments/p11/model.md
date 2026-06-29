# Model

*The developer's index into where P11 content lives, its place as PETRA III's first MX beamline, and the record of what is deliberately deferred. First cut.*

P11 is a descriptor-and-docs scaffold today, reverse-engineered from P11's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p11/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p11/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface (shared with P01, P04, P06); P11 adds the MX / bio-imaging Practices |
| Upstream source | [P11 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P11 reuses the MX Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; MX reuses the pending i03 `mx_data_collection` slug, bio-imaging the `tomography` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P11 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P11 new

P11 is a fourth beamline at an existing Site, and PETRA III's first macromolecular-crystallography beamline. Its science is high-throughput rotation MX (a crystal on a goniometer, cryostream-cooled, read by a Pilatus) plus coherent / full-field bio-imaging. At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level.

## No new families (the MX spine reuses the i03 precedent)

P11 coins no new Family. The cryostream binds the graduated `TemperatureController`; the area detector binds `Camera`; the fluorescence detector binds `EnergyDispersiveSpectrometer`; the optics and experiment-hutch motions bind `LinearStage`. Nothing in the catalog changes. The MX technique reuses the pending i03 `mx_data_collection` Method (as MANACA and TPS 07A do), and the bio-imaging reuses `tomography`.

## The honest limitation: a sparse registry

Unlike P01 (named monochromators, KB mirrors) and P06 (named hexapods, Maia), the P11 OnlineXML does not label its goniometer or MX instruments: most of its devices are area-grouped motor banks (`oh_mot*`, `eh1/eh2/eh3_mot*`, the piezo bank). So this cut models the experiment hutch as grouped positioning stages with the MX instrument structure carried as a question (`MX-1`), rather than inventing a goniometer the registry does not name. This is the same posture the thinner reverse-engineered scaffolds take (FAXTOR's no-manifest, TPS 05A's inferred namespace): model what the source supports, flag the rest.

## The control plane

P11 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, with the whole beamline on one Tango host (`haspp11oh`). The handles are read from P11's public OnlineXML registry and carried confirm (`CTRL-1`). The rotation-MX acquisition (the goniometer oscillation coupled to the Pilatus) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A.

## Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML exposes no undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`).** The monochromator, mirrors, and slits are not individually labelled; the oh bank is grouped.
- **The goniometer / MX structure (`MX-1`).** The registry does not name the goniometer; the eh banks are grouped, the MX instrument carried as a question.
- **The motor-bank axis roles (`GROUP-1`).** The banks carry no per-axis role; grouped as stage Assets.
- **The sample changer (`ROBOT-1`).** Not in the registry; would be a deferred sample-exchange Procedure, not a device.
- **The detector model (`DET-1`).** The Pilatus variant and the geometry are named, not bound.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The MX Methods (`TECH-1`).** Whether MX and bio-imaging enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p11_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
