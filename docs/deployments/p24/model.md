# Model

*The developer's by-kind index: where each CORA aggregate's P24 content lives, its single-crystal chemical crystallography distinct from the MX beamlines, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P24 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

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
