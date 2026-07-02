# Model

*The developer's by-kind index: where each CORA aggregate's P23 content lives, a deliberately thin in-situ / operando diffraction model, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P23 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

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
