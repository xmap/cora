# Governance

*Who will act at ISR, and the trust shape that will gate it. A deliberately partial first cut.*

Governance at ISR follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

ISR is not yet driven by CORA, so this shape is not yet instantiated. As a partial modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#who-acts-here), shared with the rest of the fleet (`GOV-1`).

## The safety boundary

The safety tier is the other piece that is not yet settled, and the source is especially thin here: **no PSS search-and-secure permit signal, photon shutter, or hutch-interlock device is in the profile collection** (the only two-button-shutter use is the filter-bank actuation, not a beam shutter). So the Enclosure permit leaves and the interlock structure are carried pending and not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

ISR adds the hazard classes that come with its instruments. Those land with the equipment that brings them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| Hard X-ray beam | the [optics](inventory.md) and [endstation](inventory.md) enclosures (XF:04ID) (`ENC-1`) | (`PSS-1`) |
| Vacuum optics | the [Source](beamline.md) walk | (`SUP-1`) |
| In-situ sample environments (when present) | the [Sample](equipment/sample.md) side | (`INSITU-1`) |

The hard X-ray beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The in-situ sample environments that ISR's name implies (electrochemistry, gas, temperature, cryostat) would each bring their own hazards, but none is in the source yet, so they are carried against the in-situ question, not invented (`INSITU-1`).

## When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when ISR's profile collection firms up past its current optics-first state and the deployment approaches the point where CORA drives ISR, following the [2-BM governance](../2-bm/governance.md) shape. Because ISR shares the NSLS-II EPICS and ophyd floor with the rest of the fleet, it re-tests the Site and Federation kernel rather than introducing a new trust model. The Zone groups the same optics and endstation resources the [inventory](inventory.md) lists; the Policies bind to the NSLS-II operator roles carried pending at the Site (`GOV-1`).
