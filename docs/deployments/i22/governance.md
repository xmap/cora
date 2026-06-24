# Governance

*Who would act at I22, and the trust shape that would gate it. Design-phase.*

Governance at I22 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

I22 introduces the third Site CORA models, after APS and MAX IV. Unlike 7-BM (which reused the existing APS envelope) and like TomoWISE (which created MAX IV), I22 requires a new Diamond Site: the facility, its operator pool, its safety review structure, and its safety forms are all Diamond-specific and carried pending on the [Diamond Site page](../diamond/index.md) until staff confirm them. None of this is in dodal, which is a controls library, not an organizational record.

Because I22 is a modelling exercise rather than a pilot, the concrete trust shape is not instantiated. What is already settled is the boundary, the same as for every deployment: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them. The Diamond personnel safety system (PSS) clearance is carried pending because its form names are not confirmed (PSS-1).

One governance note is specific to the off-roadmap nature of this exercise: whether Diamond becomes a real CORA Site at all is itself an open question (SCOPE-1). Until it is answered, the Diamond Site exists as a design-phase fixture that exercises the second-Site machinery (a new Facility, new principals, new clearances) without committing CORA to operate there.

The concrete Zone, Conduit, and Policy instances, and the Diamond operator pool, would land if and when the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.
