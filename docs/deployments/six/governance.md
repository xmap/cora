# Governance

*Who will act at SIX, and the trust shape that will gate it. First cut.*

Governance at SIX follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

SIX is not yet driven by CORA, so this shape is not yet instantiated. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md) (`GOV-1`).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md), not on the beamline, and the beamline links up to them. SIX adds hazard classes the hard X-ray fleet does not carry: ultra-high vacuum and the cryostat's cryogens at the sample environment, which an experiment Clearance would carry; those land with the instruments that bring them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives SIX, following the [2-BM governance](../2-bm/governance.md) shape.
