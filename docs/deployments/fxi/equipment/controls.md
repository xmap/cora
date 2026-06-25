# Controls

*The trigger hardware and the drive-electronics boxes, and the seam between CORA and the EPICS floor.*

## Triggering: the Zebra

FXI uses a Zebra FPGA position-capture box (`class FXIZebra` / `ZebraPositionCapture`, PV `XF:18ID-ES:1{Dev:Zebra1}:`) for hardware-timed fly tomography. It reads the sample rotary as an encoder and emits position-compare pulses:

| Wiring | Path |
| --- | --- |
| Encoder in | `enc1 = pi_r` (sample rotary), `enc2 = sx`, `enc3 = sy` |
| Pulse out | `PC_PULSE -> TTL1 -> camera`, `TTL2 -> fast shutter` |

This is the NSLS-II analog of 2-BM's Aerotech PSO: the gating is in hardware, off the rotary position, so projection triggers stay aligned with rotation angle independent of software jitter. CORA arms and configures the Zebra over the `ControlPort`; it does not generate the pulses. A second box (`Zebra2`) is referenced in source but only `Zebra1` is instantiated (ZEBRA-1).

## Motion controllers

The EpicsMotors above are driven by controller boxes whose identity (model, protocol, axis count, serial, firmware, IP) lives in the IOC instance config, not the profile collection. CORA records them as families only, pending (DRIVE-1):

| Controller | Drives | Notes |
| --- | --- | --- |
| `SampleMotionController` | `XF:18IDB-OP*` sample-side motors | box identity unknown |
| `OpticsMotionController` | `XF:18IDA-OP*` optics motors | box identity unknown |

This was investigated and is not settleable from public open source: FXI publishes only two repos (`fxi-profile-collection` and `fxi-workflows`), with no IOC-config repo. NSLS-II deploys IOCs through the `NSLS2/nsls2.ioc_deploy` Ansible device-role collection plus per-beamline `<bl>-epics-containers` repos (only `cms-epics-containers`, a test beamline, is public), but FXI's per-beamline IOC inventory, which would bind a controller model and IP to each motor group, is ops-private. The generic driver modules exist in the org (`I404-ioc`, `mdrive-ioc`, `mcs-ioc`, `pi-e621-ioc`), but none binds FXI's hardware. So DRIVE-1 needs FXI staff or private inventory access, not more searching.

## The seam: CORA and the floor

This is where CORA's design meets the FXI floor. The seam has the same shape as 2-BM's, with NSLS-II hardware on the floor side.

CORA **owns** (its Conductor, over the `ControlPort`):

- the scan orchestration: arming the position-trigger, rotating the sample, collecting projections, taking flat and dark references, and moving back. CORA's Conductor runs this directly; it replaces the beamline's current scan orchestration rather than calling into it.
- the energy change: the coupled move that holds magnification constant (see [Recipes](../recipes.md)) is a Conductor leg.
- the decision of what to run, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs, via the ophyd hardware abstraction (`Device.read()/set()/trigger()`): this is the `ControlPort` boundary, the handles CORA commands the hardware with;
- the Zebra FPGA position-compare gating (the trigger pulses are generated in hardware off the rotary encoder);
- the DCM PID feedback (`-Ax:Th2}PID.FBON`, `-Ax:Chi2}PID.FBON`), the PSS/PPS interlock, the camera IOCs, and the motion-controller IOCs;
- the facility filestore where the detector's raw frames physically land. CORA's transfer leg moves frames from there over its `TransferPort` into CORA's own Dataset of record; CORA records the Dataset, it does not adopt the facility's data catalog (see [Experiment > Datasets](../experiment.md#datasets)).

So CORA brings one conducting engine to FXI, working over three ports: scan orchestration over the ControlPort, reconstruction over the ComputePort, and data egress over the TransferPort into the CORA Dataset. Each does work the beamline's software stack does today; CORA does it as its own design, against the same floor.

The software IOCs (`Andor`, `Kinetix`, `Marana`, `Manta`, `Zebra`, `ioLogik`) are referenced by PV namespace only, never registered as Assets.
