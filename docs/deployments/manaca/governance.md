# Governance

*Who will act at MANACA, and the trust shape that will gate it. First cut.*

Governance at MANACA follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [Sirius Site](../sirius/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

MANACA is Sirius's first MX beamline but not CORA's first Sirius deployment (the [MOGNO](../mogno/index.md) tomography scaffold precedes it): the operator pool and the safety-review structure are carried pending on the [Sirius Site](../sirius/index.md#who-acts-here), shared across the facility's beamlines, until LNLS staff confirm them (`GOV-1`). MANACA is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives MANACA, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. LNLS publishes no per-beamline personnel-safety permit signals or photon / front-end shutters, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [Sirius Site](../sirius/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

MANACA also carries the hazard classes that come with an MX endstation: a cryostream and its liquid-nitrogen supply, and an automated sample changer moving in the experiment hutch. Those land with the instruments that bring them; the sample-changer custody loop is modelled as a Procedure with a Subject thread (`ROBOT-1`), not as an Asset CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives MANACA, following the [2-BM governance](../2-bm/governance.md) shape.
