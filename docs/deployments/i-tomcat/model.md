# Model

*The developer's index into where I-TOMCAT content lives. Modelling exercise.*

I-TOMCAT is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i-tomcat/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i-tomcat/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/psi/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/psi/site.yaml) | the PSI facility surface |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | no new Family: every device reuses an existing catalog Family (`InsertionDevice`, `Monochromator`, `Mirror`, `Filter`, `Window`, `Slit`, `Shutter`, `RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `Objective`, `Housing`, `TimingController`) or an allowlisted loose family (`StorageRing`, `SlipRing`) |
| Catalog Model | not bound | the vendor part numbers read from the public pages (Aerotech ABRX150, the pco.edge / pco.dimax cameras, the PSI GigaFRoST) are carried as "(target)" in the descriptor notes pending confirmation, not bound as catalog Models (DET-1, STAGE-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers I-TOMCAT Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

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

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
