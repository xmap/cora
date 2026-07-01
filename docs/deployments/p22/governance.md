# Governance

*Who will act at P22, and the trust shape that will gate it. First cut.*

Governance at P22 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P22 is CORA's fourteenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P22 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P22, following the [2-BM governance](../2-bm/governance.md) shape.

A P22-specific governance wrinkle: P22 **shares its optics chain with P09** (`SHARED-1`). The undulator, monochromator, mirrors, and phase retarder are P09 devices, so the optics-enclosure access state and the source-conditioning commands couple the two beamlines. How CORA's Federation / Trust model carries that coupling (a shared Zone, or a coordination Conduit between the two beamlines) is part of the open question; for this first cut the shared optics are homed in the P22 optics enclosure with the relationship flagged.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). The shared optics mean the optics-enclosure permit is coupled with P09.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P22, following the [2-BM governance](../2-bm/governance.md) shape.
