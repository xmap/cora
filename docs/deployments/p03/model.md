# Model

*The developer's by-kind index: where each CORA aggregate's P03 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P03 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

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
