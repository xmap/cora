# Model

*The developer's by-kind index: where each CORA aggregate's P64 content lives, its dilute high-rate fluorescence EXAFS via a large multi-element detector, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P64 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P64 new

P64 is a ninth beamline at an existing Site, and the advanced half of the PETRA III XAS pair (with the applied [P65](../p65/index.md), sharing the optics host). Its distinguishing capability is dilute, high-rate fluorescence EXAFS via a large multi-element detector. At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level.

## No new families

P64 coins no new Family. The undulator binds `InsertionDevice`; the Tsai mono `Monochromator`; the mirrors `Mirror`; the slits `Slit`; the sample / picomotor stages `LinearStage`; the Lambda detectors `Camera`; the multi-element fluorescence detector `EnergyDispersiveSpectrometer`. Nothing in the catalog changes. The 104-channel SIS3302 is grouped into one `EnergyDispersiveSpectrometer` Asset, not 104 Assets.

## The control plane

P64 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the Tsai-geometry DCM with its coupled undulator energy axis, the NewFocus picomotors, and the multi-element SIS3302 fluorescence detector. The handles are read from P64's public OnlineXML registry and carried confirm (`CTRL-1`); the optics host is shared with P65. The XAS acquisition (the continuous energy fly-scan read against the multi-element fluorescence) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the BMM / ISS XAS seams.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The energy axis is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The Tsai DCM crystal cut and the mirror coatings are carried confirm-pending.
- **The sample-bank axis roles (`GROUP-1`).** The `exp_mot` / `dac_*` bank carries no per-axis role; grouped, with the DAC sub-stage noted.
- **The detector detail (`DET-1`).** The multi-element element count, the deadtime / ROI handling, and the transmission ion chambers are named, not fully bound.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **`xas_spectroscopy` Method (`TECH-1`).** Whether XAS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p64_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
