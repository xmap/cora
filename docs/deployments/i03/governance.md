# Governance

*Who would act at I03, and the trust shape that would gate it. Design-phase.*

Governance at I03 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

I03 is the second beamline at the Diamond Site (after I22), so it reuses the Diamond facility envelope rather than creating a new one: the Diamond operator pool, the safety review structure, and the safety forms are facility-wide and inherited. I03 adds only its own beamline-bound principals, carried pending on the [Diamond Site page](../diamond/index.md). This is the same reuse pattern 7-BM follows at APS, the opposite of the new-Site work I22 did.

Because I03 is a modelling exercise, the concrete trust shape is not instantiated. What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them. The Diamond PSS clearance is carried pending because its form names are not confirmed (PSS-1).

One governance shape is sharper at I03 than at the other deployments: **autonomous sample handling**. The sample-changing robot would run unattended, so its operation must be gated. Following the 19-BM precedent (ROBOT-1), CORA models this as a Clearance that must be Active before the robot may load, issued after a separate safety review of the changer. The robot is one Positioner-presenting Asset; the autonomy is governed by the Clearance, and the sample it carries is tracked as a `Subject` through a custody lifecycle, not as part of the device. None of that is built yet; the seam is reserved, not invented (ROBOT-1).

The off-roadmap question SCOPE-1 applies here as at I22: whether Diamond becomes a real CORA Site is unanswered. The concrete Zone, Conduit, and Policy instances, the operator pool, and the robot Clearance would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.
