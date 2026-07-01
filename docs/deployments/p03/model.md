# Model

*The developer's index into where P03 content lives, its place as PETRA III's first SAXS / WAXS beamline, and the record of what is deliberately deferred. First cut.*

P03 is a descriptor-and-docs scaffold today, reverse-engineered from P03's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p03/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p03/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface (shared with P01, P04, P06, P11); P03 adds the scattering Practices |
| Upstream source | [P03 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P03 reuses the optics / motion / detector Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; SAXS / WAXS reuse the pending `small_angle_scattering` / `wide_angle_scattering` slugs (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P03 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P03 new

P03 is a fifth beamline at an existing Site, and the fleet's entry into small-angle / wide-angle scattering. It is the MiNaXS beamline: micro- and nanofocus SAXS / WAXS at 9-23 keV across two endstations (the microfocus endstation and the nanofocus GINIX endstation with its waveguide nano-focusing). It brings a two-endstation-sharing-one-optics-chain layout, the shared P02 / P03 high-heatload optics, and two new Tango motion-controller protocols (Galil DMC slit controllers, SmarPod controllers), but no new Family or Method.

## No new families (the scattering instrument reuses existing vocabulary)

P03 coins no new Family. The multilayer monochromator binds `Monochromator`; the mirrors bind `Mirror`; the CRL and GINIX hexapods bind `Hexapod`; the waveguide stages bind `LinearStage`; the slits bind `Slit`; the sample rotation binds `RotaryStage`; the sample environment binds `TemperatureController`; the detectors bind `Camera` / `EnergyDispersiveSpectrometer`; the shutter binds `Shutter`. Nothing in the catalog changes.

## The control plane

P03 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, and adds two controller protocols new to the set: Galil DMC slit controllers and SmarPod controllers (the GINIX waveguide). The handles are read from P03's public OnlineXML registry and carried confirm (`CTRL-1`); the shared P02 / P03 optics mean the first defining slit reports on the P02 host (`HOST-1`). The SAXS / WAXS acquisition (the sample scan coupled to the Pilatus, the GINIX waveguide-scanning nano-imaging) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics physical detail (`OPT-1`).** The multilayer d-spacing, the mirror coatings, and the CRL / waveguide focal sizes are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The `expmi_mot` and `mot` banks carry no per-axis role in the registry; grouped as sample-stage Assets, roles pending.
- **The GINIX geometry (`SAMPLE-1`).** The waveguide-to-sample geometry and the sample-hexapod / rotation detail are pending.
- **The detector roster (`DET-1`).** The SAXS-vs-WAXS detector assignment, the sample-to-detector distance, and the detector models are named, not fully bound.
- **The host mapping (`HOST-1`).** The shared P02 / P03 optics host and the bare-host Lambda are flagged; whether shared Tango DB or registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The scattering Methods (`TECH-1`).** Whether SAXS / WAXS enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p03_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
