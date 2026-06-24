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

## The seam: CORA and the EPICS floor

FXI's seam has the same shape as 2-BM's, with NSLS-II names.

CORA **replaces** (moves into the Conductor over `ControlPort`):

- the bluesky scan plans (`fly_scan`, `tomo_zfly`, `radiography_scan`, `xanes_scan`); the fly-scan staging ceremony (arm Zebra, rotate, poll, collect, take flat/dark, move back) is Conductor scope;
- the energy-change choreography `move_zp_ccd_xh`;
- the queue-server orchestration authority (CORA decides what to run; the RunEngine stays the floor executor).

CORA **drives through** (stays on the floor):

- ophyd `Device.read()/set()/trigger()` over the EPICS IOCs (the bluesky `Msg` vocabulary is the `ControlPort` contract);
- the Zebra FPGA position-compare gating;
- the DCM PID feedback (`-Ax:Th2}PID.FBON`, `-Ax:Chi2}PID.FBON`), the PSS/PPS interlock, the AreaDetector camera IOCs, and the motion-controller IOCs;
- the Tiled write path and the `/nsls2/data/...` filestore (the Porter reads it, does not own it).

The three edge runtimes map onto FXI's bluesky stack one-to-one: Conductor = RunEngine / queue-server, Reckoner = TomoPy reconstruction, Porter = the Prefect end-of-run workflow exporting to Tiled.

The software IOCs (`Andor`, `Kinetix`, `Marana`, `Manta`, `Zebra`, `ioLogik`) are referenced by PV namespace only, never registered as Assets.
