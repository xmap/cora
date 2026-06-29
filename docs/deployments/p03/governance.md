# Governance

*Who will act at P03, and the trust shape that will gate it. First cut.*

Governance at P03 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P03 is CORA's fifth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#who-acts-here), shared across the facility's beamlines (with P01, P04, P06, P11), until DESY staff confirm them (`GOV-1`). P03 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P03, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the shared optics and the two endstations) and the interlock structure are carried pending and are not invented here (`PSS-1`). The nanofocus GINIX experiment shutter is read from the registry but its safety role is not (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

A P03-specific governance note: P03 shares its high-heatload optics with P02, so the optics enclosure's safety and access state is coupled to the neighbouring beamline; how the shared-optics permit is modelled is part of the `HOST-1` / `PSS-1` questions.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P03, following the [2-BM governance](../2-bm/governance.md) shape.
