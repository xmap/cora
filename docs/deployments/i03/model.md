# Model

*The developer's index into where I03 content lives. Design-phase.*

I03 is a documentation-and-descriptor scaffold: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i03/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i03/beamline.yaml) | the device walk, with the dodal-derived EPICS PV handles; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; I03 added to its beamlines, with MX practices carried pending |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | **one Family graduated: `Goniometer`** (pending to defined, the Smargon as canonical instance). I03 also reuses existing Families and carries loose families (`StorageRing` and 2-BM's `Diagnostic` reused; `Backlight` new). `TemperatureController` (the cryostream / thawer) was loose here too but has since graduated to a catalog Family (presenting `Regulator`) on the i11 rule-of-three; `FluxMonitor` (the Flux / IPin readouts) likewise graduated, presenting the Sensor Role, on the i22/i03/i15-1 rule-of-three |
| Catalog Capability / Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the MX data-collection, grid-scan, and sample-exchange Methods are deferred until the technique enters scope (TECH-1) |
| Catalog Model | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none bound; dodal names hardware (Dectris, Oxford Cryosystems, the robot) but no part is procured |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers I03 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md), including the robot Clearance gate |

## The one catalog change: graduating Goniometer

I03 is the first Diamond deployment to earn a new catalog Family. The catalog had carried `Goniometer` as pending (documented, not yet defined). I03's `Smargon` is CORA's first canonical six-axis MX goniometer (omega / chi / phi rotation plus x / y / z sample-centring, with centre-of-rotation control), so it is the deployment that graduates Goniometer from pending to a defined Family. The Family stays a bare role-noun; chi-vs-kappa and axis-count variants are per-Asset settings or a bound Model, not Family splits. The per-axis decomposition and centre-of-rotation calibration are carried pending (GONIO-1).

## What is deliberately not here yet

- **New Capabilities / Methods and vendor Models.** I03 graduates Goniometer (an already-pending Family with a canonical instance) but earns no new Capabilities or Methods in this scaffold; the MX recipes are carried pending. No catalog Model is bound.
- **The robot as a Family.** An adversarial new-kind review refuted a `SampleChanger` Family: the robot is one Positioner-presenting Asset (the 19-BM / 32-ID position), with the sample a `Subject` and autonomy a Clearance. The robot's shape is deferred to ROBOT-1, not minted.
- **Integration scenarios.** No `test_i03_*.py` registers I03 Assets. Hard-registering a design-phase, off-roadmap beamline would commit speculative structure.
- **The endstation Assembly.** The goniometer + aperture-scatterguard + backlight + cryostream are carried flat; an MX-endstation Assembly (the 2-BM SampleTower analogue) is promoted only when a feature must act on the whole (ASSEMBLY-1).
- **Operations and experiment views.** A runbook for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
