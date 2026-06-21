# Controls

*The control stack and trigger scheme. Design-phase; handles not yet assigned.*

TomoWISE runs on the MAX IV control stack, Tango with Sardana and PandABox-class hardware (the same family as the DanMAX collaboration), not the EPICS stack 2-BM uses. This is the single biggest control difference from the APS pilot.

## Device handles

CORA models each device's control handle as an opaque string set at the edge, independent of the control system. For TomoWISE the Tango/Sardana device and attribute names are not yet assigned, so every device's handle is left empty in the [descriptor](../inventory.md) rather than filled with an invented value. Wiring each Asset to a real handle is tracked by CTRL-1 on [Open questions](../questions.md).

The EPICS-shaped `pv` field that the descriptor schema carries for the APS pilot is simply omitted here; if typed Tango handles are later required, the schema gains a control-system-neutral handle field at that point, not before.

## Triggering

The rotary stage (RT100AX target) is the master clock: its TTL encoder emits 3600 pulses per revolution, expected to feed the camera trigger inputs directly. The TDR specifies no FPGA conditioner, in contrast to 2-BM's softGlueZynq box. This may evolve once the camera trigger requirements firm up (TRIG-1).

The trigger chain is modelled as a single `TimingController` device carrying the scheme; the conditioner question stays open until the cameras are chosen (DET-1).
