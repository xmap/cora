# Governance

*Who will act at P61, and the trust shape that will gate it. First cut.*

Governance at P61 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P61 is CORA's seventeenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#who-acts-here), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P61 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P61, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). P61 carries hazard classes specific to a high-energy white-beam / Large Volume Press beamline: the unmonochromated white beam (a stringent shielding / interlock case) and the LVP's high-pressure / high-temperature environment. Those land with the instruments that bring them when the deployment firms up; the press is modelled as a sample-environment `PressureCell` Asset when exposed, not a beam-steering device CORA drives.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P61, following the [2-BM governance](../2-bm/governance.md) shape.
