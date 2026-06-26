# Governance

*Who will act at LIX, and the trust shape that will gate it. First cut.*

Governance at LIX follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

LIX is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The profile collection's access model is a POSIX-ACL `login` keyed to a proposal id, not a facility role roster, so the NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#who-acts-here), shared with the rest of the fleet (`GOV-1`).

## The safety boundary

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are largely absent from the beamline's profile collection (only the photon-shutter enable status is present), so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

LIX adds the hazard classes that come with its instruments, and one that is distinctive: a wet, biological sample environment. Those land with the equipment and the samples that bring them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| Hard X-ray beam | the [optics](inventory.md) and [endstation](inventory.md) enclosures (XF:16IDA / B / C) (`ENC-1`) | (`PSS-1`) |
| Vacuum optics and the SAXS flight path | the [Source](beamline.md) walk and the detector translations | (`SUP-1`) |
| Biological samples, buffers, and pressurized fluidics | the [Sample](equipment/sample.md) delivery chain (the HPLC pump, the buffers, the flow cell) | (`FLUID-1`, `SEC-1`) |

The hard X-ray beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The vacuum extent and the cooling supply that the optics and flight path depend on are carried pending (`SUP-1`). The biological-sample and pressurized-fluidics hazards are distinctive to a life-science solution beamline and travel with the delivery chain and the Subject; they are carried pending against the fluidic questions, not invented (`FLUID-1`, `SEC-1`).

## When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives LIX, following the [2-BM governance](../2-bm/governance.md) shape. Because LIX shares the NSLS-II EPICS and ophyd floor with the rest of the fleet, it re-tests the Site and Federation kernel rather than introducing a new trust model. The one new wrinkle is the fluidic delivery chain: a Conduit would have to bind the HPLC cart's heterogeneous surfaces (the soft-IOC, the Moxa sockets) as command surfaces alongside EPICS, the same multi-transport Conduit shape the [MX3](../mx3/governance.md) deployment first surfaced. The Zone groups the same optics and endstation resources the [inventory](inventory.md) lists; the Policies bind to the NSLS-II operator roles carried pending at the Site (`GOV-1`).
