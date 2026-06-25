# Governance

*Who will act at 9-ID, and the trust shape that will gate it. First cut.*

Governance at 9-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

9-ID is not yet driven by CORA, so this shape is not yet instantiated. The 9-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation (a placeholder `9-ID Beamline Scientist` is carried pending on the [APS Site](../aps/index.md#who-acts-here)).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them. 9-ID's hazard classes are within the X-ray and vacuum envelope of the optics-and-detector beamlines; user-brought sample environments on the CSSI stack would carry their own hazards on an experiment Clearance, landing with the instruments that bring them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 9-ID, following the [2-BM governance](../2-bm/governance.md) shape.
