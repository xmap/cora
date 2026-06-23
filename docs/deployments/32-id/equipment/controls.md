# Controls

*The control stack and access path. Design-phase; handles not yet assigned.*

32-ID runs on the APS EPICS control stack, the same floor as the 2-BM pilot. CORA observes that floor and, where it replaces TomoScan-style scan and alignment orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. The 32-ID source docs do not publish the PV handles, drive crates, or IOC hosts for the modelled devices, so every device's handle is left empty in the [descriptor](../inventory.md) rather than filled with an invented value. Wiring each Asset to a real handle is tracked by `CTRL-1` on [Open questions](../questions.md).

## Access

The TXM is operated from the `TXMTWO` workstation, reachable remotely over `delos.aps.anl.gov` with an APS badge and an active proposal. This is the operator's entry point to the EPICS user interface; CORA records it as context, not as a modelled control path.

## Triggering

The TXM trigger and timing scheme (the camera and stage synchronization during a tomographic scan) is not published in the source docs and is not modelled here. It joins, as a `TimingController` device, once the scan hardware and PVs are confirmed (`CTRL-1`, `TXM-1`).

## Equipment protection

32-ID carries a BLEPS equipment-protection interlock separate from the personnel PSS, as 2-BM does. CORA does not model the interlock logic; it would only observe outcomes, mapping utility faults to Supply status and device faults to an Asset condition. That mapping is `BLEPS-1` on [Open questions](../questions.md).
