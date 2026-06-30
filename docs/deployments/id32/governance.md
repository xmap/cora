# Governance

*Who will act at ID32, and the trust shape that will gate it. First cut.*

Governance at ID32 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

ID32 is CORA's first ESRF deployment, so the ESRF is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [ESRF Site](../esrf/index.md#who-acts-here), shared across the facility's beamlines, until ESRF staff confirm them (`GOV-1`). ID32 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives ID32, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The ESRF personnel-safety permit signals and the photon and front-end shutters are absent from the BLISS Beacon config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ESRF Site](../esrf/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

ID32 adds the hazard classes that come with its endstations: a 9 Tesla superconducting magnet and its liquid-helium cryogen plant at the XMCD endstation, and an intense polarized soft X-ray beam. Those land with the instruments that bring them, and an experiment Clearance would carry them; the magnet and its cryogens are modelled as hazards on the experiment, not as Assets CORA drives for safety (the LASER-1 / sample-environment precedent).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives ID32, following the [2-BM governance](../2-bm/governance.md) shape.
