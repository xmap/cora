# Controls

*The control stack and trigger scheme. Design-phase; handles not yet assigned.*

19-BM runs on the APS EPICS stack, the same control system as the 2-BM pilot, and is expected to follow the 2-BM TomoScan and MCTOptics IOC layout. This is the opposite of TomoWISE, which runs MAX IV Tango/Sardana; for 19-BM the established 2-BM control idioms should transfer.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For 19-BM the EPICS PV names are not yet assigned, so every device's handle is left empty in the [descriptor](../inventory.md) rather than filled with an invented value. Wiring each Asset to a real PV is tracked by CTRL-1 on [Open questions](../questions.md).

## Triggering

19-BM is built for high-throughput autonomous CT, so triggering and sync are load-bearing. The sample rotary stage is the candidate master clock; whether its encoder feeds the camera triggers directly, and whether PSO-style fly-scan triggering is used, is to be confirmed (TRIG-1). The chain is modelled as a single `TimingController` device carrying the scheme.

## Equipment protection (BLEPS)

Separate from the personnel safety system (PSS), the Beamline Equipment Protection System (BLEPS, ICMS APS_2388098) guards the hardware: it interlocks the gate valve to the beamline vacuum sensors, monitors the cooling water plumbed in series across the Be window and the photon stop (loss of flow trips both protections at once), and commands the front-end exit valve closed on a downstream vacuum breach.

CORA does not model a dedicated equipment-protection aggregate. Following 2-BM, the vacuum and cooling water are facility Supplies whose faults the BLEPS folds into the beam-availability signal the pre-flight gate reads; the exact mapping is an [open question](../questions.md) (BLEPS-1). PSS and BLEPS stay distinct seams: one gates people, the other protects equipment.
