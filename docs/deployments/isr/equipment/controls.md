# Controls

*The control stack, the early-commissioning signals, and the absent mission devices. A deliberately partial first cut; handles read from the profile collection, carried confirm.*

ISR runs on the NSLS-II EPICS / ophyd control stack, the same floor as the rest of the NSLS-II fleet. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The control handles are filled from the beamline's own bluesky profile collection ([NSLS2/isr-profile-collection](https://github.com/NSLS2/isr-profile-collection), the `startup/` files), so the descriptor carries the real PV roots. The optics zones carry the DCM (`XF:04IDA-OP:1{Mono:DCM}`, `MONO-1`), the focusing pair and the harmonic-rejection mirror (`Mir:HFM/VFM/DHRM`, `OPT-1`), and the undulator gap (`SR:C04-ID:G1{IVU:1}`, `SRC-1`); the zone-D endstation carries the filter bank (`XF:04IDD-ES{Fil:1-4}`, `ATTN-1`), the two bound sample axes (`Dif:ISD-Ax:th/zeta`, `DIFF-1`), and the Eiger 1M (`XF:04IDD-ES{Det:Eig1M}`, `DET-1`). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

## Early-commissioning signals

The profile collection reads as an early / commissioning scaffold, and CORA models it honestly rather than papering over the gaps:

- several devices are **commented out** (the QuadEM flux-monitor electrometers, the secondary-source slit), so they are not modelled (`DET-1`, `OPT-2`);
- the resonant **energy axis is a non-functional stub** (the energy-scan plan calls a placeholder lookup), so no energy pseudo-axis is modelled (`RESONANT-1`);
- the databroker catalog has a **placeholder name** and the Eiger writes to a `testing/` path, both commissioning signals (`CTRL-1`);
- and the multi-circle **diffractometer** and the **in-situ environment** are absent entirely (`DIFF-1`, `INSITU-1`).

These are carried as open questions, not invented. As the beamline's profile firms up, the deployment grows to match.

## The orchestration seam

The ISR acquisition runs through bluesky plans (a `th` rocking scan, attenuated scans over `zeta`), software / EPICS-triggered step scans; there is no Zebra, no Struck scaler, and no hardware fly-trigger in source. The data plane uses bluesky-queueserver and Tiled. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it, and keeps its own data-of-record. When the diffractometer lands, CORA would conduct the orientation and detector-arm moves and the reciprocal-space scans over that engine (`DIFF-1`).

## Equipment protection

No PSS search-and-secure permit signal, photon shutter, or hutch-interlock device is in the profile collection (the only two-button-shutter use is the filter-bank actuation, not a beam shutter). The permit leaves and the safety tier are carried pending and not invented here (`PSS-1`). If CORA later models the protection tier, it would observe outcomes, not the interlock logic.
