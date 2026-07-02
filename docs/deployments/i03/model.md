# Model

*The developer's by-kind index: where each CORA aggregate's I03 content lives, the one catalog Family it graduates (`Goniometer`), and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I03 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## The one catalog change: graduating Goniometer

I03 is the first Diamond deployment to earn a new catalog Family. The catalog had carried `Goniometer` as pending (documented, not yet defined). I03's `Smargon` is CORA's first canonical six-axis MX goniometer (omega / chi / phi rotation plus x / y / z sample-centring, with centre-of-rotation control), so it is the deployment that graduates Goniometer from pending to a defined Family. The Family stays a bare role-noun; chi-vs-kappa and axis-count variants are per-Asset settings or a bound Model, not Family splits. The per-axis decomposition and centre-of-rotation calibration are carried pending (GONIO-1).

## What is deliberately not here yet

- **New Capabilities / Methods and vendor Models.** I03 graduates Goniometer (an already-pending Family with a canonical instance) but earns no new Capabilities or Methods in this scaffold; the MX recipes are carried pending. No catalog Model is bound.
- **The robot as a Family.** An adversarial new-kind review refuted a `SampleChanger` Family: the robot is one Positioner-presenting Asset (the 19-BM / 32-ID position), with the sample a `Subject` and autonomy a Clearance. The robot's shape is deferred to ROBOT-1, not minted.
- **Integration scenarios.** No `test_i03_*.py` registers I03 Assets. Hard-registering a design-phase, off-roadmap beamline would commit speculative structure.
- **The endstation Assembly.** The goniometer + aperture-scatterguard + backlight + cryostream are carried flat; an MX-endstation Assembly (the 2-BM SampleTower analogue) is promoted only when a feature must act on the whole (ASSEMBLY-1).
- **Operations and experiment views.** A runbook for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).
