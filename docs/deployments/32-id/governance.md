# Governance

*Who will act at 32-ID, and the trust shape that will gate it. Design-phase.*

Governance at 32-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

32-ID is a design-phase scaffold in CORA, so this shape is not yet instantiated. The 32-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation; CORA does not invent a 32-ID operator roster.

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them rather than restating them. 32-ID adds hazard classes beyond the 2-BM tomography envelope, a class-4 laser on the additive-manufacturing rig, pressurized helium and cryogens, that an experiment Clearance would carry; those land with the instruments that bring them, which are deferred (see [Model](model.md#deliberately-not-here-yet)).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 32-ID, following the [2-BM governance](../2-bm/governance.md) shape.
