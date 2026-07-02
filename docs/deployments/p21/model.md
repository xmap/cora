# Model

*The developer's by-kind index: where each CORA aggregate's P21 content lives, a deliberately thin Swedish-collaboration materials model, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P21 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P21 new

P21 is a thirteenth beamline at an existing Site, a Swedish-collaboration high-energy materials beamline (P21.1 powder / total scattering, P21.2 diffraction / imaging). At the modelling level it is a reuse-and-reinforce deployment, and a deliberately thin one given its sparse registry slice.

## No new families (a thin, honest model)

P21 coins no new Family. The motor banks bind `LinearStage`; the slits bind `Slit`; the detectors are a pending `Camera` placeholder. Nothing in the catalog changes. The P21 registry slice exposes little beyond grouped motor banks, so the detectors are carried pending rather than invented (`DET-1`), the same model-what-the-source-supports posture as P11 / P65.

## The control plane

P21 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, split across three Tango hosts (`hasep212oh`, `hasep21eh3`, `haspp21lab`). The handles are read from P21's public OnlineXML registry and carried confirm (`CTRL-1`). The high-energy diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML slice exposes no undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`).** The monochromator, mirrors, and slits within the optics bank are not labelled; grouped.
- **The motor-bank axis roles (`GROUP-1`).** The `oh_u*`, `eh3_u*`, `lab*` banks carry no per-axis role; grouped as stage Assets.
- **The detectors (`DET-1`).** Not in the registry slice; carried as a pending `Camera` placeholder.
- **The P21.1 station (`HOST-1`).** The `hasep211eh` host exposed only bookkeeping devices; noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Methods (`TECH-1`).** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p21_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
