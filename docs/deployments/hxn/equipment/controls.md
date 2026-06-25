# Controls

*The trigger box and the motion controllers, and the seam between CORA and the floor.*

Unlike FXI, HXN exposes its motion controllers in the profile collection, so CORA can model them as families (the box models, firmware, and IPs are still pending, DRIVE-1).

## Triggering: the Zebra

HXN uses a Zebra FPGA position-capture box (`nanoZebra`, class `SRXZebra`, `XF:03IDC-ES{Zeb:3}:`) to hardware-gate the per-point detector triggers off the scan position during a 2D fly raster, the same position-compare role the Aerotech PSO plays at 2-BM and the Zebra plays at FXI. A fast shutter sits on a second Zebra (`Zeb:2`). A PandABox is being introduced (`67-nano-panda`, partly commented in source) as a go-forward timing box; CORA carries it deferred (ZEBRA-1).

## Motion controllers

| Asset | Family | Drives |
| --- | --- | --- |
| `SampleMotionController` | MotionController | Power PMAC (`Ppmac:1`) for the fine raster axes, plus `MC:2`-`MC:8` |
| `NanoPositioningController` | MotionController | Attocube `ANC350:1`-`ANC350:8` for coarse nano-positioning, OSAs, beam stops |

HXN names these controllers in source (the PMAC and Attocube boxes), so they are modelled as `MotionController` Assets with the vendor evident; the box model, firmware, serials, and IPs remain staff questions (DRIVE-1). This is more than FXI exposed, where the controller layer was ops-private.

## The seam: CORA and the floor

This is where CORA's design meets the HXN floor. The shape matches FXI's, with HXN's scanning twist.

CORA **owns** (its Conductor, over the `ControlPort`):

- the scan orchestration: emitting a 2D/3D raster trajectory over the fine sample axes, hardware-gated point by point by the Zebra, and reading the multi-modal detector set per point. CORA's Conductor runs this directly; it replaces the beamline's current scan orchestration.
- the energy change, which co-moves the monochromator and the zone-plate refocus (ENERGY-1).
- the decision of what to run, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the Zebra position-compare gating (the per-point pulses are generated in hardware off the scan position);
- the PMAC and Attocube closed-loop stage feedback, the PSS/PPS interlock, and the detector IOCs;
- the facility filestore where the detectors' raw frames and spectra land. CORA moves them, over the `TransferPort`, into CORA's own Dataset of record; CORA records the Dataset, it does not adopt the facility's data catalog.

So CORA brings one conducting engine to HXN, working over three ports: raster orchestration over the `ControlPort`, reconstruction over the `ComputePort` (ptychographic phase retrieval is the heavier multi-step compute leg here, beyond tomographic reconstruction), and data egress over the `TransferPort` into the CORA Dataset.

The software IOCs (`Merlin`, `Eiger`, `Dexela`, `Xspress3`, `Zebra`, `PandA`, `MCS`) are referenced by PV namespace only, never registered as Assets.
