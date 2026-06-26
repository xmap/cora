# Controls

*The rotation motion, the Zebra trigger box, the motion controllers, and the seam between CORA and the floor.*

## Rotation data collection

AMX's defining operation is a rotation (oscillation) data collection: the goniometer omega sweeps a vector trajectory while the Eiger captures frames, gated by a hardware trigger. A PowerBrick vector controller runs the goniometer vector and the `Zebra` FPGA (`XF:17IDB-ES:AMX{Zeb:1}`, with a second at `{Zeb:2}`) captures position and fans out the triggers to the Eiger. The fast grid scan for crystal location uses the same vector + Zebra path. CORA would model the sweep as conducting a Run, with the vector as a held trajectory.

## Motion controllers

The goniometer vector and grid-scan motion run on a PowerBrick / PPMAC; the remaining axes (mirrors, slits, sample stages) are standard EPICS motor records. The controller box models, firmware, and IPs are not reliably in the profile collection (the profile's PowerBrick vector PV is misconfigured to the FMX prefix), so `MotionController` is carried as a `MotionController` family with the specifics blank (DRIVE-1).

## The seam: CORA and the floor

This is where CORA's design meets the AMX floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the acquisition: setting the energy, centring the crystal, running the rotation or grid-scan vector, and collecting the Eiger under the gated trigger;
- the autonomous loop: the EMBL-robot load / centre / collect / unmount sequence as a Procedure over the spine, threaded through the `Subject` custody lifecycle and gated by the [trust boundary](../governance.md#the-trust-boundary) (ROBOT-1);
- the choice of technique, energy, and program, and the beam-centre / energy calibrations.

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the LSDC Governor robot/human state machine, the PowerBrick vector and Zebra triggering, the bimorph mirror shaping, the Eiger and Mercury detector IOCs, and the PSS interlock;
- the facility filestore where the per-run data lands. CORA moves it, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to AMX, working over the ports: acquisition over the `ControlPort`, the per-technique reduction (indexing, integration, scaling, phasing) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset.

The software systems (`LSDC`, `mxtools`, the EMBL robot, the Governor, the Eiger IOC, the Mercury DXP) are referenced by PV namespace only, never registered as Assets.
