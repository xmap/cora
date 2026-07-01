# Governance

*Who will act at P02, and the trust shape that will gate it. First cut.*

Governance at P02 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P02 is CORA's eighth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P02 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P02, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the OH1 optics and the two endstations) and the interlock structure are carried pending and are not invented here (`PSS-1`). A P02-specific note: P02 owns the OH1 high-heatload optics hutch shared with P03, so the optics enclosure's access state couples to the neighbouring beamline, part of the `PSS-1` question.

P02 also carries the hazard classes that come with its endstations: a high-energy (~60 keV) beam, in-situ furnaces (the Anton-Paar) at P02.1, and the diamond-anvil-cell high-pressure environment at P02.2. Those land with the instruments that bring them when the deployment firms up; the pressure cell is modelled as a sample-environment `PressureCell` Asset, not a beam-steering device CORA drives.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P02, following the [2-BM governance](../2-bm/governance.md) shape.
