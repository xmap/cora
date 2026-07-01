# Governance

*Who will act at P07, and the trust shape that will gate it. First cut.*

Governance at P07 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P07 carries a governance wrinkle the other PETRA III beamlines do not: it is **jointly operated by Helmholtz-Zentrum Hereon (2/3) and DESY (1/3)** (`OPERATOR-1`). How that joint operation maps to CORA's Federation / Trust model (a single Site with a shared operator pool, or two Federation participants sharing a beamline) is a facility-governance question carried pending. For this first cut, P07 is modelled as a beamline on the PETRA III Site, with the Hereon stake noted on the [index](index.md) and as a question; the DESY / Hereon operator pool and safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance) (`GOV-1`).

P07 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P07, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the optics and the two experiment hutches) and the interlock structure are carried pending and are not invented here (`PSS-1`). P07 also carries the hazard classes that come with its endstations: a high-energy beam, the 17 T superconducting magnet and its liquid-helium cryogen, and the Linkam furnace; those land with the instruments that bring them when the deployment firms up.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P07, following the [2-BM governance](../2-bm/governance.md) shape.
