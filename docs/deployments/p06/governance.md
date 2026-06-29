# Governance

*Who will act at P06, and the trust shape that will gate it. First cut.*

Governance at P06 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P06 is CORA's third PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#who-acts-here), shared across the facility's beamlines (with P01 and P04), until DESY staff confirm them (`GOV-1`). P06 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P06, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the mono hutch and the two probe endstations) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

P06 also carries the hazard classes that come with a dense nano-probe endstation: hexapods, KB-lens stacks, and piezo scanners moving in close quarters inside interlocked hutches. Those land with the instruments that bring them when the deployment firms up.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P06, following the [2-BM governance](../2-bm/governance.md) shape.
