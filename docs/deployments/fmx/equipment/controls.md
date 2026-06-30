# Controls

*The rotation vector controller, the Zebra trigger box, the motion controllers, and the seam between CORA and the floor.*

## Rotation data collection

FMX's defining operation is a rotation (oscillation) data collection: the goniometer omega sweeps a vector trajectory while the Eiger captures frames, gated by a hardware trigger. The `VectorMotionController` (a PowerBrick, `XF:17IDC-ES:FMX{Gon:1-Vec}`, with a PPMAC fast-motion channel `XF:17ID-CT:FMX{MC17:Sender}`) runs the goniometer vector (start / end / expose / hold), and the `Zebra` FPGA (`XF:17IDC-ES:FMX{Zeb:3}`) captures position and fans out the triggers to the Eiger (the mxtools `MXFlyer`). The fast grid scan for crystal location uses the same vector + Zebra path. CORA would model the sweep as conducting a Run, with the vector as a held trajectory.

## Motion controllers

The goniometer vector and grid-scan motion run on the PowerBrick / PPMAC; the remaining axes (mirrors, slits, sample stages) are standard EPICS motor records. The controller box models, firmware, and IPs are not fully in the profile collection (DRIVE-1), so `VectorMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the FMX floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the acquisition: setting the energy, centring the crystal, running the rotation or grid-scan vector, and collecting the Eiger under the gated trigger;
- the autonomous loop: the robot load / centre / collect / unmount sequence as a Procedure over the spine, threaded through the `Subject` custody lifecycle and gated by the [trust boundary](../governance.md#the-trust-boundary) (ROBOT-1);
- the choice of technique, energy, and in-situ program, and the beam-centre / energy calibrations.

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the LSDC Governor robot/human state machine, the PowerBrick vector and Zebra triggering, the bimorph mirror shaping, the Eiger and Mercury detector IOCs, and the PSS interlock;
- the facility filestore where the per-run data lands. CORA moves it, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to FMX, working over the ports: acquisition over the `ControlPort`, the per-technique reduction (indexing, integration, scaling, phasing) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset.

The software systems (`LSDC`, `mxtools`, the Governor, the Eiger IOC, the Mercury DXP, the PowerBrick) are referenced by PV namespace only, never registered as Assets.
