# Governance

*Who will act at HEX, and the trust shape that will gate it. First cut.*

Governance at HEX follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

HEX is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#who-acts-here), shared with the rest of the fleet (`GOV-1`).

## A distinct allocation policy

HEX has one governance fact the other NSLS-II beamlines do not: a share of its beamtime is reserved for proposals aligned with New York clean-energy and energy-storage goals. Public sources describe a portion of beamtime set aside for such proposals, evaluated by a dedicated proposal-evaluation committee on weighted criteria (technical merit, New York commercial relevance, economic development, and personnel), with the remainder allocated through the standard NSLS-II proposal review and all proposals administered through the facility proposal system. This is a real, distinct trust-shape input: an allocation Policy that gates which experiments run, layered on top of the facility-wide safety and access tiers.

CORA records this as a Policy-level fact, not a new bounded context or descriptor. The exact reservation fraction and the committee's scoring split are carried as a world-fact (`GOV-1`) and are modelled when CORA drives the beamline, not instantiated now. The allocation Policy binds to the NSLS-II operator and review roles carried pending at the Site.

## The safety boundary

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the beamline's profile collection, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

HEX adds the hazard classes that come with its instruments. Those land with the equipment that brings them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| High-energy hard X-ray beam (white to 250 keV, monochromatic to 200 keV) | the [optics](inventory.md) and [endstation](inventory.md) enclosures (`hex-foe`, `hex-endstation`) | (`PSS-1`, `SCW-1`) |
| The superconducting wiggler source | the [Source](beamline.md) walk (cryogen-free, no liquid-helium hazard) | (`SCW-1`) |
| Heavy-sample handling (up to 500 kg) | the [Sample](equipment/sample.md) tower | (`STAGE-1`) |
| User-brought in-situ / operando environments | the [Sample](equipment/sample.md) endstation | (`INSITU-1`) |

The high-energy beam is the interlocked hazard, and at these photon energies the shielding burden is heavier than the fleet's lower-energy beamlines; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The superconducting wiggler is cryogen-free, so no liquid-helium supply hazard is carried (`SCW-1`). The heavy-sample handling and the user-brought in-situ environments are operational hazards carried with the equipment that brings them (`STAGE-1`, `INSITU-1`); none is invented, each is recorded against its question.

## When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives HEX, following the [2-BM governance](../2-bm/governance.md) shape. Because HEX shares the NSLS-II EPICS and ophyd floor with its siblings, it re-tests the Site and Federation kernel rather than introducing a new trust model. The Zone groups the same optics and endstation resources the [inventory](inventory.md) lists; the Conduit binds the command surfaces; the Policies bind to the NSLS-II operator roles carried pending at the Site, with the NYSERDA-aligned allocation Policy layered on top (`GOV-1`).
