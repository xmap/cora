# Controls

*The control stack and the orchestration seam. Diamond EPICS / ophyd-async, with the dodal-derived handles for the coherence-branch endstation recorded. A deliberately partial first cut: only the endstation is in the module.*

I13-1 runs the Diamond EPICS control stack driven through ophyd-async, the same floor as the other dodal-modelled Diamond beamlines. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS. As at the other Diamond beamlines, the control handles are read from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library, which records the real EPICS PV root for each device. The honest scope caveat sits at the top: the dodal `i13_1` module exposes **only** the coherence-branch endstation, so this scaffold carries handles for the sample stage and the two cameras and nothing upstream. The shared I13 source and optics (the undulator, monochromator, mirrors, and slits) are not in the module and are deferred, not invented (SRC-1, OPT-1).

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For I13-1 the EPICS PV roots are read from dodal (`src/dodal/beamlines/i13_1.py`) and carried `confirm`, because a controls-library snapshot is not a guarantee against the live system (CTRL-1). The handles follow the Diamond convention, a PV root that encodes a functional zone rather than a hutch, all on the `BL13J` prefix of the coherence branch:

| Asset | Family | PV root | What it does |
| --- | --- | --- | --- |
| `SampleStage` | [`LinearStage`](../../../catalog/families.md) | `BL13J-MO-PI-02:` | the PI piezo sample-scanning stage; the ptychography raster is its operative motion (SAMPLE-1) |
| `SideCamera` | [`Camera`](../../../catalog/families.md) | `BL13J-OP-FLOAT-03:` | the Aravis / GenICam optical viewing camera, for sample alignment (DET-1) |
| `Detector` | [`Camera`](../../../catalog/families.md) | `BL13J-EA-DET-04:` | the Merlin / Medipix3 photon-counting area detector, recording the far-field coherent-diffraction pattern (DET-1) |

The fixed-angle lab-frame variant of the sample stage (`BL13J-MO-PI-02:FIXANG:`) is a setting on the same stage, not a second Asset (SAMPLE-1). The full handle list, Asset by Asset, is in the [Inventory](../inventory.md), and the source walk that binds each one is the generated [Source](../beamline.md) page.

What dodal does **not** give for I13-1, and so is not invented here:

- the shared source and optics: the module starts at the endstation, so there is no undulator, monochromator, mirror, or slit Asset to carry, and none is coined (SRC-1, OPT-1). The machine state above the branch is observed as a loose `StorageRing`, observe-only, with the source-side control story left to a later cut (MACHINE-1).
- which access-gated enclosure the endstation maps to: the PV prefix encodes a functional zone, not the coherence-branch hutch or its safety meaning (ENC-1).
- the calibrated values behind the handles, and the supporting infrastructure around the endstation (SUP-1).

## The orchestration seam

The ptychography acquisition is the seam a CORA edge replaces. Today it runs as bluesky plans over ophyd-async / EPICS: a raster scan of the PI piezo sample stage coupled to the Merlin far-field capture, the coherent beam stepped across the sample point by point while the photon-counting detector records the diffraction pattern at each position. That raster-coupled-to-capture loop is the orchestration CORA's edge conducts over the same floor, driving through ophyd-async rather than EPICS owning the loop.

This is CORA's first coherent lensless-imaging deployment. The novelty is an acquisition shape and a reconstruction, not a device class: the devices are a raster `LinearStage` plus `Camera`s, so no new device Family is coined. Ptychography / CDI is carried as a new pending Method, the fleet's first coherent diffractive imaging (TECH-1), with the Site Practice `I13-1_ptychography_practice` carried pending alongside it.

The downstream image reconstruction is not a beamline device. Recovering the real-space image from the recorded far-field diffraction stack is `ComputePort` work, the coherent-imaging analogue of the reconstruction legs at the imaging beamlines, run over the port rather than modelled as an endstation Asset.

### The seam: CORA and the floor

This is where CORA's design meets the I13-1 floor. The shape matches the other dodal-modelled Diamond beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the ptychography acquisition: emitting the raster trajectory over the PI piezo sample stage, coupling it to the Merlin far-field capture, and reading the diffraction frames through the series;
- the choice of technique and timing, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd-async device layer (dodal): the PI sample stage, the side camera, the Merlin detector, the `ControlPort` boundary;
- the shared source and optics once they are in scope and PV-bound (SRC-1, OPT-1);
- the detector file-writing to the Diamond filestore, where the Merlin far-field frames land. That is plumbing CORA observes; CORA moves the frames, over the `TransferPort`, into CORA's own Dataset of record, and records the Dataset rather than adopting the facility's data catalog.

So CORA brings one conducting engine to I13-1, working over the ports: the ptychography raster over the `ControlPort`, the image reconstruction (the diffraction-stack to real-space-image retrieval) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset. The reconstruction is a clean `ComputePort` leg, not a beamline device (TECH-1).

The software IOCs (`Merlin`, the GenICam camera) are referenced by interface only, never registered as Assets.

## Equipment protection

The PSS search-and-secure permit signals, the photon and front-end shutters, and any interlock tier are **absent from the `i13_1` dodal module** and are not invented here (PSS-1). dodal is a device-control library, not a safety-system description: the coherence-branch module carries the endstation motion and camera handles, not the permit leaves behind an interlocked hutch. CORA names neither a permit signal nor a shutter for I13-1 until the beamline team supplies them. This is the same partial-first-cut posture the rest of the page takes: the shutters and interlocks live upstream with the shared source and optics that are also out of this cut (SRC-1, OPT-1).

The Enclosure permit shape for the coherence-branch hutch and the hazard tier are carried pending at the Diamond Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../diamond/index.md#the-safety-envelope)). The Diamond operator pool and review are pending at the Site (GOV-1), and Clearances are issued at the Diamond Site.

See [Open questions](../questions.md) for the control, detection, and safety items still to confirm, and [Model](../model.md#deliberately-not-here-yet) for the deferred source and optics decisions and the pending ptychography Method (TECH-1).
