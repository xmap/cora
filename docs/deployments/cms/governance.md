# Governance

*Who will act at CMS, and the trust shape that will gate it. First cut.*

Governance at CMS follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

CMS is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#who-acts-here), shared with the rest of the fleet (GOV-1).

## The safety boundary

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the beamline's profile collection, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (PSS-1). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

CMS adds the hazard classes that come with its instruments. Those land with the equipment that brings them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| Hard X-ray beam | the [optics](inventory.md) and [endstation](inventory.md) enclosures (XF:11BMA, XF:11BMB) (ENC-1) | (PSS-1) |
| Vacuum optics and the telescoping flight path | the [Source](beamline.md) walk and the detector translations | (SUP-1) |
| In-situ temperature environments | the [Sample](equipment/sample.md) thermal / tensile stage | (TEMP-1) |

The hard X-ray beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (PSS-1). The vacuum extent and the cooling supply that the optics and flight path depend on are carried pending (SUP-1), and the in-situ temperature range that the Linkam stage brings is carried with it (TEMP-1). None of these is invented; each is recorded against its question.

## When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives CMS, following the [2-BM governance](../2-bm/governance.md) shape. Because CMS shares the NSLS-II EPICS and ophyd floor with FXI, HXN, SRX, BMM, SIX, CHX, ESM, and its twin SMI, it re-tests the Site and Federation kernel rather than introducing a new trust model. The Zone groups the same optics and endstation resources the [inventory](inventory.md) lists; the Conduit binds the command surfaces; the Policies bind to the NSLS-II operator roles carried pending at the Site (GOV-1).
