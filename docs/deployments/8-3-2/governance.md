# Governance

*Who will act at 8.3.2, and the trust shape that will gate it. First cut.*

Governance at 8.3.2 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ALS Site](../als/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

8.3.2 is CORA's first ALS deployment, so ALS is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [ALS Site](../als/index.md#who-acts-here), shared across the facility's beamlines, until ALS staff confirm them (`GOV-1`). 8.3.2 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives 8.3.2, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. ALS publishes no per-beamline personnel-safety permit signals or photon / front-end shutters, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ALS Site](../als/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 8.3.2, following the [2-BM governance](../2-bm/governance.md) shape.
