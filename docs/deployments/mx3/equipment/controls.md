# Controls

*The shutters, the motion controllers, and the seam between CORA and the floor, which at MX3 is a heterogeneous control plane.*

## Shutters and triggering

The `WhiteBeamShutter` (`MX3FE01SHT01`) and `MonoBeamShutter` (`MX3BLSH01SHT01`) are PSS photon shutters gating the beam into the hutch; an MD3 fast shutter (Exporter-driven) gates the per-oscillation exposure at the sample. The rotation collection is the goniometer omega sweep synchronized with the Eiger frames; the concrete trigger wiring is part of the recipe layer (deferred at this design phase).

## Motion controllers

The endstation and detector stages run on Australian Synchrotron Power Brick (PMAC) motion controllers (the `MX3STG..MOT..` axis records, class `ASBrickMotor`); their firmware and IPs are not in the library (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and a heterogeneous floor

MX3 is where CORA's `ControlPort` meets its most varied floor yet. Where the other deployments are single-control-plane (EPICS over Channel Access, via ophyd), MX3 is **four planes at once**, and the seam is the same in shape but wider in span.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the rotation-MX collection: setting the energy, positioning the detector distance, orienting the crystal on the goniometer, and arming and triggering the detector through the oscillation;
- the autonomous sample-exchange loop (the ISARA robot) as a Procedure, and the choice of what to collect, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace), now across four transports:

- **EPICS** (via ophyd) for the monochromator, attenuator, shutters, cryojet, flux and beam-position monitors, OAV camera, and the Power Brick stages, the `ControlPort` boundary CORA already knows.
- the **MXCuBE Exporter protocol** (TCP) for the MD3 microdiffractometer goniometer and its sub-devices; CORA treats the Exporter client as a `ControlPort` adapter.
- the **SIMPLON REST API** (HTTP) for the DECTRIS Eiger; the arm / trigger / disarm / config lifecycle is a `ControlPort` adapter over REST, the first non-EPICS detector in the fleet.
- the **ISARA TCP client** for the sample robot, driven by the sample-exchange Procedure.

The point for CORA is that the `ControlPort` abstraction holds: the same conducting engine drives MX3 over four transports without a new domain model, only new adapters. Data egress (the Eiger frames) moves over the `TransferPort` into CORA's Dataset of record, and any reduction (indexing / integration) is `ComputePort` work.

The software interfaces (`DECTRIS-SIMPLON`, `MD3-Exporter`, `ISARA-robot`, `BlackFly`, the MD3 Redis camera) are referenced by interface only, never registered as Assets.
