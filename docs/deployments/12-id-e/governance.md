# Governance

*Who will act at 12-ID-E, and the trust shape that will gate it. First cut.*

Governance at 12-ID-E follows the same model as the other APS beamlines: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

12-ID-E is not yet driven by CORA, so this shape is not yet instantiated. As a reverse-engineered scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The instrument config exposes device tables, not the human roster, so the APS operator pool and safety-review structure is carried pending at the [APS Site](../aps/index.md#who-acts-here), shared across the beamlines (`GOV-1`).

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the instrument config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them rather than restating them. 12-ID-E adds the hazard classes that come with a hard X-ray USAXS endstation under vacuum and the in-situ temperature environments at the sample (the Linkam T96 and PTC10 stages, `TEMP-1`); those land with the instruments that bring them, and an experiment Clearance would carry them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 12-ID-E, following the [2-BM governance](../2-bm/governance.md) shape.
