# Governance

*Who will act at ID28, and the trust shape that will gate it. First cut.*

Governance at ID28 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

ID28 is CORA's second ESRF beamline, so the ESRF Site already exists (established with ID32): the operator pool and the safety-review structure are carried pending on the [ESRF Site](../esrf/index.md#who-acts-here), shared across the facility's beamlines, until ESRF staff confirm them (`GOV-1`). ID28 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives ID28, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The ESRF personnel-safety permit signals and the photon and front-end shutters are absent from the BLISS Beacon config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ESRF Site](../esrf/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

ID28 adds the hazard classes that come with its endstation: a cryogenic sample environment (the 10 K displex cryostat and the cryogens it draws on) and a hard X-ray beam. Those land with the instruments that bring them, and an experiment Clearance would carry them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives ID28, following the [2-BM governance](../2-bm/governance.md) shape.
