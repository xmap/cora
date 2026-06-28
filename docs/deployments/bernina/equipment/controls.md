# Controls

*The control stack, the beam-synchronous timing, the event-driven DAQ, and the externalized configuration. Design-phase, with the `eco`-derived handles recorded.*

Bernina runs the PSI EPICS stack for slow control, plus the SwissFEL event-driven DAQ for the per-shot data. As at [Alvra](../../alvra/equipment/controls.md), the control handles are **known where they are inline**: PSI's [`eco`](https://github.com/paulscherrerinstitute/eco) library records the real EPICS PV prefix for most devices in `eco/bernina/bernina.py`, so this scaffold carries `pv` on those devices. But Bernina differs from Alvra in one important way, recorded below.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For Bernina the EPICS PV prefixes are recorded from `eco`, carried `confirm`. The PV naming is the SwissFEL convention keyed by section, `SARFE10-` for the Aramis front end, `SAROP21-` for the Aramis optics (note: the `SAROP21` line, distinct from Alvra's `SAROP11`), and `SARES2x-` / `SLAAR21-` for the Bernina endstation and laser. The full handle list is in the [Inventory](../inventory.md).

What `eco` does not give, and so is not invented: the motor units and limits (these live on the EPICS records at runtime), which access-gated hutch each device sits in (the prefix encodes a beamline-line section, ENC-1), and the Aramis source parameters. One `eco`-specific ambiguity is recorded rather than resolved: a live Bernina profile monitor references an Alvra-line PV (`SAROP11-PPRM066`), which may be a real shared device or a copy-paste residue (XREF-1).

## The externalized configuration (CONFIG-1)

This is the control fact that makes Bernina a deliberately partial first cut, and it is specific to this station. `eco`'s `eco/bernina/config.py` has its entire device list commented out and loads it at runtime from a non-public path (`/sf/bernina/config/eco/bernina_config_eco.json`). The live module then reads a second non-public config (`/sf/bernina/config/eco/configuration/bernina_config.json`) for the per-diffractometer flags that decide which sub-assemblies are mounted (base / arm / polana / kappa / heavy-load / hexapod / robot) and which detectors attach to each platform.

So the public source gives the device list (the inline `bernina.py` `append_obj` calls) and the diffractometer axis topology (`bernina_diffractometers.py`, where axes are built by literal PV suffix), but not the configuration state. CORA models the shape and carries the state unknown (CONFIG-1). This is the honest scope line; a later cut or a staff confirmation fills it without re-deriving the topology. It contrasts with i13-1's partial cut (where the upstream source was simply absent from the module) and with Alvra's (where the manifest was complete): Bernina's manifest is complete in shape but externalized in state.

## Timing and triggering

Timing is handled by the **SwissFEL event system**: a master timing node (`SIN-TIMAST-TMA`), a CTA sequencer (`SAR-CCTA-ESB`), and EVR (event-receiver) units distribute a beam-synchronous trigger pattern, with the pulse-ID read from `SARES20-CVME-01-EVR0:RX-PULSEID`. CORA models the event timing as a `TimingController`, the same Family the 2-BM Timing device, the Diamond / APS PandABoxes, the LCLS EventSequencer, and the Alvra EVRs use.

The Family fits the device; what does not fit is the trigger-pattern content. "Acquire on event-code N at beam rate R" is a typed acquisition concept with no home in CORA's timing model, which today knows only `Internal` / `ExternalEdge` / `ExternalLevel` trigger modes. The trigger pattern would be carried as opaque setpoints until a typed parameter shape is earned (TIMING-1). This is the timing half of the per-shot acquisition gap, the same one Alvra and LCLS-MFX reach.

## The floor: sf-daq, bsread, the eco suite, and the robot

A seam observation, recorded for the eventual Conductor work. Bernina's acquisition floor is `sf-daq` (the per-shot, pulse-ID-tagged event acquisition broker), `bsread` / `mflow` (the beam-synchronous ZMQ streaming transport), the `eco` / `slic` Python scan and acquisition suite (the layer this descriptor is mined from), the non-public `bernina_config` JSON (the device list, diffractometer mount state, and detector wiring, CONFIG-1), and the Staeubli TX200 sample / detector robot over PShell HTTP (ROBOT-1), all listed in the descriptor's `software_iocs_not_modeled`.

These are control-system software, not CORA Assets. They are recorded because they are what a future CORA Conductor would orchestrate over or reference. As at Alvra, the `sf-daq` event-driven, pulse-ID-correlated data plane is the hardest test of that seam: CORA does not poll it but references it. The shape that reference takes (a `Dataset` handle, with the Run as the provenance envelope) is sketched in the [event-stream-axis design note](../model.md); the per-shot DAQ run is the deepest gap this exercise re-confirms (DAQ-1).

See [Open questions](../questions.md) for the control and timing items still to confirm.
