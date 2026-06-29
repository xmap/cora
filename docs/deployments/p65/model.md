# Model

*The developer's index into where P65 content lives, its place as the applied half of the PETRA III XAS pair, and the record of what is deliberately deferred. First cut.*

P65 is a descriptor-and-docs scaffold today, reverse-engineered from P65's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p65/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p65/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface; P64 + P65 add the XAS Practices |
| Upstream source | [P65 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P65 reuses the optics / motion Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; XAS reuses the pending `xas_spectroscopy` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P65 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P65 new

P65 is a tenth beamline at an existing Site, and the applied / high-throughput half of the PETRA III XAS pair (with the advanced [P64](../p64/index.md), sharing the optics host). Its science is routine transmission + fluorescence EXAFS / XANES. At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level, and a deliberately thin model matching its sparse registry slice.

## No new families (a thin, honest model)

P65 coins no new Family. The undulator binds `InsertionDevice`; the CDCM energy axis `Monochromator`; the stages `LinearStage`; the slit `Slit`; the table `Table`; the detection placeholder `FluxMonitor`. Nothing in the catalog changes. The P65 registry slice exposes little beyond the energy axis and the sample bank, so the detection chain is carried as a pending placeholder rather than invented (`DET-1`), the same model-what-the-source-supports posture as P11 and the thinner reverse-engineered scaffolds.

## The control plane

P65 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, sharing the optics host (`hasnp64`) with P64. The handles are read from P65's public OnlineXML registry and carried confirm (`CTRL-1`). The XAS acquisition (the CDCM energy scan read against transmission / fluorescence) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the BMM / ISS XAS seams.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The energy axis is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The CDCM crystal cut and the optics-bank breakdown are carried confirm-pending.
- **The bank axis roles (`GROUP-1`).** The `oh_*`, `fe_*`, and `a2_*` banks carry no per-axis role; grouped as stage Assets.
- **The detection chain (`DET-1`).** The ion chambers and fluorescence detector are not in the registry slice; carried as a pending `FluxMonitor` placeholder.
- **The host mapping (`HOST-1`).** The energy / optics report on the shared P64 host; modelled in the P65 optics enclosure with the host flagged.
- **The dummy stubs (`STUB-1`).** The `a2_dmy*` placeholder devices are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **`xas_spectroscopy` Method (`TECH-1`).** Whether XAS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p65_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
