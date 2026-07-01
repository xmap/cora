# Model

*The developer's index into where P22 content lives, its place as the HAXPES branch off the P09 optics, and the record of what is deliberately deferred. First cut.*

P22 is a descriptor-and-docs scaffold today, reverse-engineered from P22's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p22/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p22/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface; P22 adds the HAXPES Practice |
| Upstream source | [P22 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P22 reuses `Manipulator` / `ElectronAnalyzer` / optics Families + the catalog `PhaseRetarder` |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; HAXPES reuses the pending `angle_resolved_photoemission` slug (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P22 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P22 new

P22 is a fourteenth beamline at an existing Site, the facility's hard X-ray photoemission (HAXPES) beamline. Its distinguishing structural fact is that it **shares its optics chain with P09**: the undulator, DCM, mirrors, phase retarder, and absorber are P09 devices, and P22 is the HAXPES branch off that chain. At the modelling level it is a reuse-and-reinforce deployment, plus a shared-optics relationship the Federation / Trust model would carry.

## No new families

P22 coins no new Family. The shared optics bind `Monochromator` / `Mirror` / `Filter` and the catalog `PhaseRetarder` (P22 is the third consumer, the one that completed the 4-ID/P09/P22 rule-of-three); the HAXPS sample stage binds `Manipulator` (the NSLS-II ESM Family); the electron analyzer binds the catalog `ElectronAnalyzer` (also ESM, carried pending here). Nothing in the catalog changes.

## The control plane

P22 sits on the PETRA III Tango device floor with Sardana as the scan layer. Its defining control fact is the shared P09 optics (the `p09/` addresses), so P22's source-conditioning state is coupled to P09 (`SHARED-1`). The handles are read from P22's public OnlineXML registry and carried confirm (`CTRL-1`); the electron analyzer is a self-contained instrument not in the registry slice (`DET-1`). The HAXPES acquisition runs as a Sardana macro coordinated with the analyzer; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The shared-optics relationship (`SHARED-1`).** P22 and P09 share the undulator / DCM / mirrors / phase retarder; how that maps to CORA's Federation / Trust coordination (two beamlines, one optics chain) is pending.
- **The undulator parameters (`SRC-1`).** The gap is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The DCM crystal cut, the mirror coatings, and the phase-retarder geometry are carried confirm-pending.
- **The manipulator axis roles (`GROUP-1`).** The `p22/motor` bank carries no per-axis role; grouped as one `Manipulator`.
- **The electron analyzer (`DET-1`).** The defining HAXPES detector is named (bound to `ElectronAnalyzer`) but its model / control interface is not in the registry; carried pending.
- **The dummy stubs (`STUB-1`).** The `haxps_dmy*` placeholder devices are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The HAXPES Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p22_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
