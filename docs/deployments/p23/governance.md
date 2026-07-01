# Governance

*Who will act at P23, and the trust shape that will gate it. First cut.*

Governance at P23 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P23 is CORA's fifteenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P23 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P23, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). P23's in-situ / operando sample environments (electrochemical cells, growth chambers) may carry their own hazards; those land with the instruments that bring them when the deployment firms up.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P23, following the [2-BM governance](../2-bm/governance.md) shape.
