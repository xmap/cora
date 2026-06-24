# Governance

*Who would act at I15-1, and the trust shape that would gate it. Design-phase.*

Governance at I15-1 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take, gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the command surfaces, and Policies).

I15-1 is the third beamline at the Diamond Site (after I22 and I03), so it reuses the Diamond facility envelope: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited. I15-1 adds only its own beamline-bound principals, carried pending on the [Diamond Site page](../diamond/index.md).

Two governance points are worth noting at I15-1:

- **The interlocks are governance data, not equipment.** dodal exposes a PSS hutch interlock and a goniometer interlock. CORA does not model these as Assets: an interlock is the read-only permit behind the **Enclosure** aggregate (the shipped Enclosure BC), so it is carried as the Enclosure `permit_signal`, mutated by the safety system, not by CORA (INTERLOCK-1). dodal even gives real interlock PVs here (unlike I22 / I03), carried as the permit-signal candidates pending confirmation (PSS-1).
- **Autonomous sample loading is gated by a Clearance.** Like I03, the powder/capillary robot would run unattended, so its operation is gated by a Clearance that must be Active, issued after a safety review; the robot is one Positioner Asset and the sample it carries is a `Subject` (ROBOT-1).

Because I15-1 is a modelling exercise, the concrete Zone, Conduit, and Policy instances are not instantiated; the off-roadmap question SCOPE-1 applies as at I22 / I03. They would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.
