# Controls

*The control stack, the event timing, the event-driven DAQ, and the `slic` provenance. Design-phase, with the `slic`-derived handles recorded.*

Cristallina runs the PSI EPICS stack for slow control, plus the SwissFEL event-driven DAQ for the per-shot data. It differs from the sibling [Alvra](../../alvra/equipment/controls.md) and [Bernina](../../bernina/equipment/controls.md) stations in its provenance, recorded below.

## Device handles, and the `slic` source

CORA models each device's control handle as an opaque string set at the edge. For Cristallina the EPICS PV prefixes are recorded from [`slic`](https://gitea.psi.ch/slic/cristallina), carried `confirm`. The distinctive fact: Cristallina is **CORA's first deployment mined from `slic`, not `eco`**. Cristallina has no presence in `eco` at all; its controls live in the `slic` library on PSI's gitea (`gitea.psi.ch`, branch `master`), `eco`'s active successor, which is publicly reachable without login. `slic` stores the device facts as in-repo Python literals (a categorized `channels/pv_channels.py` plus `beamline/` driver classes), so this is a fuller cut than Bernina, whose `eco` config externalized its device list.

The PV naming is the SwissFEL convention keyed by section: `SARFE10-` for the shared Aramis front end, `SAROP31-` for the Cristallina Aramis optics (Alvra is `SAROP11`, Bernina `SAROP21`, Cristallina `SAROP31`), and `SARES3x-` / `SAR-EXPMX-` for the endstation. The full handle list is in the [Inventory](../inventory.md).

What `slic` does not give, and so is not invented: most motor units and limits (the exceptions actually in source are the photon-energy 5-13 keV setpoint range, the magnet field limits and ramp cap, and the LakeShore PID tables), which access-gated hutch each device sits in (ENC-1), and the Aramis undulator source curve. One provenance caution shapes the inventory: many `slic` drivers are instantiated but their PV channels are commented out of the active tuples (DM2, several SmarAct stages, the Attocube, the PuMa stack, the cameras); these are carried as present-hardware-not-acquired (DISABLED-1).

## Timing and triggering

Timing is handled by the **SwissFEL event system**: a CTA sequencer (`SAR-CCTA-ESC`) and EVR (event-receiver) units distribute a beam-synchronous trigger pattern. CORA models the event timing as a `TimingController`, the same Family the 2-BM Timing device, the LCLS EventSequencer, and the Alvra / Bernina EVRs use.

The Family fits the device; what does not fit is the trigger-pattern content. "Acquire on event-code N at beam rate R" is a typed acquisition concept with no home in CORA's timing model, which today knows only `Internal` / `ExternalEdge` / `ExternalLevel` trigger modes. The trigger pattern would be carried as opaque setpoints until a typed parameter shape is earned (TIMING-1). At Cristallina the event system carries an additional load: with no pump-probe laser device in source, the CTA sequencer and EVR also mediate the pump-probe delay directly (LASER-1), where Alvra and Bernina have a dedicated laser-timing chain.

## The floor: sf-daq, bsread, the slic suite, and the server-side services

A seam observation, recorded for the eventual Conductor work. Cristallina's acquisition floor is `sf-daq` (the per-shot, pulse-ID-tagged event acquisition broker), `bsread` / `mflow` (the beam-synchronous ZMQ streaming transport), the `slic` Python scan and acquisition suite on gitea (the layer this descriptor is mined from), and two server-side services the endstation drivers reach out to: the DilSc SECoP / Frappy magnet server (`dilsc.psi.ch:5000`, an alternative to the live EPICS magnet driver) and the pulsed-magnet pulse-tube synchronization service (`oscillations.psi.ch:8000`). All are listed in the descriptor's `software_iocs_not_modeled` (ENV-1).

These are control-system software, not CORA Assets. They are recorded because they are what a future CORA Conductor would orchestrate over or reference. As at Alvra and Bernina, the `sf-daq` event-driven, pulse-ID-correlated data plane is the hardest test of that seam: CORA does not poll it but references it. The shape that reference takes (a `Dataset` handle, with the Run as the provenance envelope) is sketched in the [event-stream-axis design note](../model.md); the per-shot DAQ run is the deepest gap this exercise re-confirms (DAQ-1).

Note the provenance contrast across the PSI set: Alvra and Bernina are mined from `eco` (a GitHub Python device library), Cristallina from `slic` (its gitea successor). That the same architectural gaps surface from both libraries, and across all three Aramis stations, is the reinforcement this third station exists to provide.

See [Open questions](../questions.md) for the control and timing items still to confirm.
