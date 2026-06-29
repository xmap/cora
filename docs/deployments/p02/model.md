# Model

*The developer's index into where P02 content lives, its place as the fleet's second diamond-anvil-cell deployment, and the record of what is deliberately deferred. First cut.*

P02 is a descriptor-and-docs scaffold today, reverse-engineered from P02's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p02/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p02/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface (shared with P01, P04, P06, P11, P03, P10, P09); P02 adds the diffraction Practices |
| Upstream source | [P02 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P02 reuses the optics / motion / detector Families + the allowlisted-loose `PressureCell` |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; powder / total scattering reuse the pending `powder_diffraction` / `total_scattering` slugs (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P02 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P02 new

P02 is an eighth beamline at an existing Site, and the fleet's high-energy diffraction beamline with two branches: P02.1 (powder / total scattering / PDF, ~60 keV) and P02.2 (extreme conditions, diamond-anvil cell). At the modelling level it brings the fleet's **second diamond-anvil-cell** endstation, reusing the allowlisted-loose `PressureCell` Family the APS 13-id-d deployment introduced.

## No new families (the DAC reuses the 13-id-d PressureCell)

P02 coins no new Family. The monochromator binds `Monochromator`; the bendable HFM / VFM mirrors bind `Mirror`; the slits bind `Slit`; the sample stages bind `LinearStage`; the sample environment binds `TemperatureController`; the detectors bind `Camera` / `EnergyDispersiveSpectrometer`; the beam monitor binds `FluxMonitor`; and the diamond-anvil cell binds the allowlisted-loose `PressureCell`. Nothing in the catalog changes.

Adding P02 as `PressureCell`'s second consumer crossed the rule-of-three promotion threshold, so the loose-family review records a promote-or-hold note (`hold: graduation-due, PRESSURE-1`), matching the `PhaseRetarder` / `PolarizationAnalyzer` / `Magnet` entries P09 and the POLAR-family beamlines carry. This is the loose-family graduation guard working as designed.

## The control plane

P02 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the bendable HFM / VFM mirrors (curvature / ellipticity attribute motors), the Pilatus 1M + PerkinElmer high-energy detectors, and the Anton-Paar / Lakeshore sample environment. The handles are read from P02's public OnlineXML registry and carried confirm (`CTRL-1`). P02 owns the OH1 high-heatload optics hutch shared with P03. The powder / total-scattering / high-pressure acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics detail (`OPT-1`).** The DCM crystal cut and the bendable-mirror coatings / focusing recipes are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The eh1a/b and eh2a/b banks carry no per-axis role; grouped as stage Assets.
- **The pressure-cell control (`PRESSURE-1`).** The diamond-anvil-cell membrane / gas-loading / pressure control is not in the registry; the `PressureCell` Family is the allowlisted-loose 13-id-d one, now graduation-due.
- **The detector roster (`DET-1`).** The detector models, the powder-vs-PDF detector roles, and the P02.2 diffraction area detector are named, not fully bound.
- **The CH dummy stubs (`STUB-1`).** The CH1 / CH2 `tangomotor` dummies are test / placeholder devices, noted not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Methods (`TECH-1`).** Whether powder diffraction / total scattering enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p02_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
