# Controls

*The control stack, the scan path, and the autofocus loop. Design-phase; handles not yet assigned.*

2-ID runs on the APS EPICS control stack, the same floor as the 2-BM pilot, with a Bluesky RunEngine submitting the raster over the EPICS scanRecord. CORA observes that floor and, where it replaces EAA's scan and autofocus orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. The EAA corpus does not publish PV handles, drive crates, or IOC hosts: its 2-ID-D launcher is a simulation, and the `aps_mic` integration addresses devices by short registry keys (`samy`, `samz`, `zp_z`), with the concrete PV strings living in beamline startup files the corpus does not include. So every device's handle is left empty in the [descriptor](../inventory.md) rather than filled with an invented value. Wiring each Asset to a real handle is tracked by `CTRL-1` on [Open questions](../questions.md).

## The scan path

The raster is a Bluesky scan over the EPICS scanRecord: a 2D fly raster (`fly2d`) or a 1D step scan (`step1d`), with the sample stage moving and the fluorescence detector and flux monitors read at each point. This is the sequencing CORA's Conductor takes over from EAA: CORA owns the Run lifecycle (start, hold, abort, close) and the durable scan state, while the hardware-triggered raster and the scanRecord IOC stay floor.

## The autofocus loop

The distinctive control loop is zone-plate autofocus: EAA acquires a 2D map, takes a line scan across a landmark feature, registers it, steps the `zp_z` focus axis, and minimises the spot width, then applies drift correction over a long scan. In CORA's model this is a conducted, multi-step move-and-measure Run with an agent in the loop: EAA registers as the [Agent](../model.md#how-eaa-fits) that proposes each focus step, each proposal becomes a Decision, and CORA's permit and clearance adjudication is the gate the proposed move passes through. EAA's own default-deny posture (operator confirmation required, motion and beam disabled by default) is the shape that gate enforces.

## Triggering

The detailed trigger and timing scheme (the detector and stage synchronization during a fly raster) is not published in the corpus and is not modelled here. It joins, as a `TimingController` device, once the scan hardware and PVs are confirmed (`CTRL-1`).

## Equipment protection

2-ID carries an equipment-protection interlock separate from the personnel PSS, as 2-BM does. CORA does not model the interlock logic; it would only observe outcomes, mapping utility faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this scaffold.
