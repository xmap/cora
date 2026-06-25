# Governance

*Who would act at I11, and the trust shape that would gate it. Design-phase.*

Governance at I11 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take, gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the command surfaces, and Policies).

I11 is the fourth beamline at the Diamond Site (after I22, I03, and I15-1), so it reuses the Diamond facility envelope: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited. I11 adds only its own beamline-bound principals, carried pending on the [Diamond Site page](../diamond/index.md).

Two governance notes at I11:

- **Autonomous sample loading is gated by a Clearance.** Like I03, the sample-changing robot + carousel would run unattended, so its operation is gated by a Clearance that must be Active, issued after a safety review; the robot is one Positioner Asset and the sample it carries is a `Subject` (ROBOT-1).
- **The TemperatureController earn touched governed vocabulary.** I11 was the rule-of-three that earned graduating the `TemperatureController` Family and a new settable-actuator Role. Because a new Role is a code change to a core BC aggregate (`SEED_ROLES`), that change was routed through the gate-review panel (3 baseline + specialist reviewers) rather than slipped into this scaffold (TEMP-1), and has since landed: `TemperatureController` is a catalog Family presenting the `Regulator` Role. The scaffold cadence stayed clean; the core-vocabulary change got its proper governance.

Because I11 is a modelling exercise, the concrete Zone, Conduit, and Policy instances are not instantiated; the off-roadmap question SCOPE-1 applies as at the other Diamond beamlines. They would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.
