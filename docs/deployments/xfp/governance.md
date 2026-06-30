# Governance

*Who will act at XFP, and the trust shape that will gate it. First cut.*

Governance at XFP follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

XFP is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. XFP is a Case Western Reserve University partner beamline operated within NSLS-II, so its operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#who-acts-here), with the partner-beamline operating model itself an open question (`GOV-1`).

## The safety boundary

The safety tier is the other piece that is not yet settled. Only the front-end photon-shutter enable status is in the beamline's profile collection (interlock-derived; plans refuse to open the shutter when it is disabled), so the Enclosure permit leaves and the rest of the search-and-secure structure are carried pending and not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

XFP brings two distinctive hazards: a high-flux white beam, and the dose it delivers. They land with the equipment and the experiment that bring them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| High-flux white / pink X-ray beam | the [optics](inventory.md) and [endstation](inventory.md) enclosures (FE:C17B, XF:17BM / XF:17BMA) (`ENC-1`) | (`PSS-1`, `WHITE-1`) |
| Delivered radiolytic dose to biological samples | the [dose-delivery gating](beamline.md) and the [Sample](equipment/sample.md) side | (`DOSE-1`, `SUBJECT-1`) |
| Vacuum white-beam optics | the [Source](beamline.md) walk | (`SUP-1`) |
| Biological samples, buffers, and fluidics | the [Sample](equipment/sample.md) delivery chain | (`FLOW-1`, `SUBJECT-1`) |

The high-flux white beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The delivered dose is itself a controlled hazard at a footprinting beamline, distinctive to its dose-delivery character, and travels with the dose-gating chain and the Subject (`DOSE-1`, `SUBJECT-1`). The biological-sample and fluidics hazards travel with the delivery chain (`FLOW-1`). None of these is invented; each is carried against its question.

## When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives XFP, following the [2-BM governance](../2-bm/governance.md) shape. Because XFP shares the NSLS-II EPICS and ophyd floor with the rest of the fleet, it re-tests the Site and Federation kernel rather than introducing a new trust model. The distinctive wrinkles are the partner-beamline operating model (`GOV-1`) and the offline-readout seam: a Conduit would bound the dose-delivery command surfaces, while the downstream mass-spec analysis sits outside the beamline's trust boundary entirely (`READOUT-1`). The Zone groups the same optics and endstation resources the [inventory](inventory.md) lists; the Policies bind to the NSLS-II operator roles carried pending at the Site (`GOV-1`).
