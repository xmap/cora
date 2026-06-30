# Controls

*The software-triggered acquisition, the two-detector plan, the motion controllers, and the seam between CORA and the floor.*

## Triggering: software, not a hardware box

A total-scattering measurement is a gated exposure on a flat-panel detector. PDF, like its twin XPD, runs the detectors in continuous or multi-trigger mode gated by the fast exposure shutter, with no separate hardware timing box in the profile collection. The two-detector, two-distance merge is sequenced by a bluesky plan (the `TwoDetectors` helper, `72-two-detector.py`): it moves one panel out, counts the static panel, moves it back, and counts the moving panel, so the near and far frames are collected in one acquisition. This is a software-sequenced acquisition, not a hardware trigger chain (DIST-1).

## Motion controllers

The optics, spinner, sample-environment, and detector-tower axes are EPICS motor records whose controller boxes, firmware, and IPs are not in the profile collection (DRIVE-1), so `EndstationMotionController` is carried as a single `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the PDF floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the total-scattering acquisition: setting the incident energy, positioning the sample on the spinner, driving the detector towers to the near and far distances, ramping the sample-environment temperature, and arming the detectors for the two-distance merge;
- the choice of technique, detector, distance, and exposure, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the side-bounce mono and mirror drives, the spinner and detector-tower motion, the cryostream / cryostat / furnace controllers, the PSS interlock, and the PerkinElmer / Pilatus detector IOCs;
- the facility filestore where the per-run frames land. CORA moves them, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to PDF, working over the ports: total-scattering orchestration over the `ControlPort`, the PDF reduction (azimuthal integration and the Fourier transform to G(r)) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset. The PDF reduction is a clean `ComputePort` leg, the total-scattering analogue of the reconstruction legs at the imaging beamlines.

The software IOCs (`PerkinElmer`, `Pilatus`, `Cryostream`, `Lakeshore`, `Linkam`, the Eurotherm) are referenced by PV namespace only, never registered as Assets.
