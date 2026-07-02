# Model

*The developer's by-kind index: where each CORA aggregate's I-TOMCAT content lives, the SLS 2.0 control-stack seam this exercise draws, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I-TOMCAT |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## The seam: what CORA would replace vs drive through

I-TOMCAT is the fleet's view of an SLS 2.0 beamline, so the control-stack boundary matters more than usual. SLS is an EPICS facility with the BEC (Beamline and Experiment Control) scan layer over ophyd introduced for SLS 2.0.

| Layer | SLS tool | CORA seam |
| --- | --- | --- |
| Control (floor) | EPICS IOCs | **drive through** (never replaced; the floor CORA actuates and observes) |
| Scan / orchestration (edge) | BEC over ophyd | **replace** (CORA's edge replaces BEC's scan/experiment steering; the BEC-shares-ophyd nuance keeps a drive-through reading open, SEAM-1) |
| Detector / capture | the camera streaming + HDF5 writer chain | **drive through / observe** (specialized capture CORA observes) |
| Data-of-record | SciCat + the Ra/SLURM Fiji reconstruction pipeline | **replace / invert source-of-truth** (CORA owns its own Dataset; SciCat is a fact a future integration reads, not CORA's record) |

This is the standard CORA lens (EPICS is the floor, the facility's scan/data software is named only to draw the boundary). The single most consequential call, BEC replace vs drive-through, is carried as SEAM-1 on [Open questions](questions.md) because BEC adopts the same ophyd device model CORA's edge would.

## What is deliberately not here yet

- **Integration scenarios.** No `test_i_tomcat_*.py` registers I-TOMCAT Assets into the event store. Scenario code is where Assets become real, and hard-registering a modelling-exercise beamline with unconfirmed facts would commit speculative structure. It lands if the deployment firms toward a real connection.
- **Vendor Models.** No catalog Model is bound. The "(target)" models in the descriptor are [open questions](questions.md), not bindings, because they are read from public pages and not staff-confirmed.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA has not connected to would be invention; see the note on the [index](index.md#not-yet-documented).
