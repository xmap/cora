# Model

*The developer's index into where P61 content lives, its place as the final OnlineXML-modelled PETRA III beamline, and the record of what is deliberately deferred. First cut.*

P61 is a descriptor-and-docs scaffold today, reverse-engineered from P61's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p61/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p61/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface; P61 adds the energy-dispersive-diffraction Practice |
| Upstream source | [P61 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61) | the beamline's own public OnlineXML Tango device registry (the `debian/stretch` branch) the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P61 reuses `LinearStage` / `EnergyDispersiveSpectrometer` |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; energy-dispersive diffraction reuses the pending `energy_dispersive_diffraction` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P61 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P61 new

P61 is a seventeenth beamline at an existing Site, the facility's high-energy white-beam wiggler beamline (P61A Large Volume Press + P61B energy-dispersive diffraction). It is the **last PETRA III beamline with a public OnlineXML registry**, completing CORA's OnlineXML-driven coverage of the facility. At the modelling level it is a reuse-and-reinforce deployment, and a deliberately thin one given its sparse registry slice (one generic motor bank).

## No new families (a thin, honest model)

P61 coins no new Family. The motor bank binds `LinearStage`; the energy-dispersive detector is a pending `EnergyDispersiveSpectrometer` placeholder. Nothing in the catalog changes. The Large Volume Press (P61A), when exposed, would reuse the allowlisted-loose `PressureCell` Family (the P02 / 13-id-d precedent); it is carried pending (`PRESS-1`). The P61 registry slice exposes little beyond the grouped motor bank, so the source, the press, and the detectors are carried pending rather than invented, the model-what-the-source-supports posture as P11 / P21 / P23.

## The control plane

P61 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, with one quirk: P61 is the only PETRA III extras package on the `debian/stretch` branch (the others are `debian/jessie`), so its snapshot vintage may differ. The handles are read from P61's public OnlineXML registry and carried confirm (`CTRL-1`). The energy-dispersive diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The source (`SRC-1`).** P61 is a damping-wiggler beamline (`source: superconducting-wiggler`); the wiggler parameters are not exposed in this registry slice.
- **The Large Volume Press (`PRESS-1`).** P61A's press is not in the registry slice; would reuse the allowlisted-loose `PressureCell` Family when exposed.
- **The motor-bank axis roles (`GROUP-1`).** The `eh_mot*` bank carries no per-axis role; grouped as one stage.
- **The detectors (`DET-1`).** The Ge energy-dispersive detector and any area detector are not in the registry slice; carried as a pending placeholder.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/stretch` (unusual for the set); some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p61_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
