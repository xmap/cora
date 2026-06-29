# Governance

*Who will act at FAXTOR, and the trust shape that will gate it. First cut.*

Governance at FAXTOR follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ALBA Site](../alba/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

FAXTOR is CORA's first ALBA deployment, so ALBA is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [ALBA Site](../alba/index.md#who-acts-here), shared across the facility's beamlines, until ALBA staff confirm them (`GOV-1`). FAXTOR is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives FAXTOR, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. ALBA publishes no per-beamline personnel-safety permit signals or photon / front-end shutters, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ALBA Site](../alba/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives FAXTOR, following the [2-BM governance](../2-bm/governance.md) shape.
