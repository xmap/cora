# Governance

*Who will act at 4-ID POLAR, and the trust shape that will gate it. First cut.*

Governance at 4-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

4-ID is not yet driven by CORA, so this shape is not yet instantiated. The 4-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation; CORA does not invent a 4-ID operator roster (a placeholder `4-ID Beamline Scientist` is carried pending on the [APS Site](../aps/index.md#who-acts-here)).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them rather than restating them. 4-ID adds hazard classes beyond the imaging envelope, superconducting magnets with high stored energy and cryogens, a pump-probe laser, and pressurized high-pressure cells, that an experiment Clearance would carry; those land with the instruments that bring them as the sample environment firms (`MAG-1`, `SAMPLE-1`).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 4-ID, following the [2-BM governance](../2-bm/governance.md) shape.
