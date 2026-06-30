# Controls

*The control stack and the orchestration seam. Design-phase, with the dodal-derived handles recorded.*

i06 runs the Diamond EPICS control stack driven through ophyd-async, the same floor as I22, I03, I15-1, I11, and I24. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS. As at the other Diamond beamlines, the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV root for each device, so this scaffold carries a handle on every Asset.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For i06 the EPICS PV roots are read from dodal (the `src/dodal/beamlines/i06.py`, `i06_shared.py`, `i06_1.py`, and `i06_2.py` factories and the `src/dodal/devices/` classes), carried `confirm` because a controls-library snapshot is not a guarantee against the live system (CTRL-1). The handles follow the Diamond convention, a PV root that encodes a functional zone rather than a hutch. The four roots i06 spans:

| PV zone | Carries | Example roots |
| --- | --- | --- |
| `BL06I` | the optics spine: PGM, the APPLE-II energy / polarization controllers, the i06-branch PEEM stage | `BL06I-OP-PGM-01:`, `BL06I-OP-IDD-01:`, `BL06I-OP-IDU-01:` |
| `SR06I` | the APPLE-II servo crates that drive the undulator gaps | `SR06I-MO-SERVC-01:` (downstream), `SR06I-MO-SERVC-21:` (upstream) |
| `BL06J` | the i06-1 diffraction-dichroism endstation | `BL06J-EA-DDIFF-01:` |
| `BL06K` | the i06-2 PEEM endstation | `BL06K-MO-PEEM-01:` |

The full handle list, Asset by Asset, is in the [Inventory](../inventory.md), and the source walk that binds each one is the generated [Source](../beamline.md) page.

What dodal does **not** give, and so is not invented: which access-gated enclosure each zone maps to (the PV encodes a functional zone, not a hutch or its safety meaning, ENC-1), and the calibrated values behind the handles.

## The APPLE-II controller seam

i06 is CORA's first APPLE-II source, so it is the first whose run drives the X-ray **polarization** as an experiment axis (linear horizontal LH / vertical LV / arbitrary-angle LA, circular positive PC / negative NC, plus third-harmonic variants) alongside the incident-energy axis. Both are modelled as `PseudoAxis` Assets over the source.

The seam to record is that the geometry already lives below CORA. An APPLE-II chooses its polarization by driving its magnetic phase rows, and the live i06 controller holds the energy-to-gap polynomial (`BL06I-OP-IDD-01:` for the downstream IDD, `BL06I-OP-IDU-01:` for the upstream IDU) and the polarization-to-phase conversion. By default that edge controller owns the kinematics:

- CORA **names** the energy and polarization pseudo-axes, **writes** the requested value, and **records** the move.
- The live i06 controller **converts** the value into gap and phase-row positions and drives the servo crates (`SR06I-MO-SERVC-01:` / `SR06I-MO-SERVC-21:`).

So the polarization pseudo-axis is carried **rule-less** (POL-1): the polarization value domain is the axis's value set, but its partition rule lives in the edge controller, not in a CORA Calibration. This is the "edge IOC already computes the geometry" seam, the same posture the energy axis takes over the PGM and gap. Pinning the conversion as a CORA-owned LookupTable Calibration is a deferred decision, needed only if CORA must scan polarization without the i06 controller in the loop (POL-1). The IDD / IDU asymmetry, only the upstream IDU exposes the driven handles in dodal, is the wiring question carried as POL-2.

## The orchestration seam

Three sequences run as bluesky plans over ophyd-async / EPICS today, and that is the seam a CORA edge replaces, conducting over the same floor:

- **Dichroism asymmetry sequences.** The XMCD / XMLD contrast comes from flipping or rotating the polarization at an absorption edge and differencing the signal. The plan steps the energy across the edge and switches the polarization pseudo-axis between states; CORA's edge would conduct that sequence over the source axes rather than EPICS owning the loop.
- **PEEM imaging.** The i06-2 acquisition sequence over the PEEM sample manipulators (`BL06K-MO-PEEM-01:`) and the i06-branch stage (`BL06I-MO-PEEM-01:`), MANIP-1.
- **Resonant soft X-ray diffraction scans.** The i06-1 scans over the diffractometer circles and detector arm (`BL06J-EA-DDIFF-01:`), with the reciprocal-space pseudo-axis as the coordinating axis (DIFF-1, DIFF-2).

In each case EPICS stays the floor and CORA's edge replaces the bluesky-style orchestration, driving through ophyd-async. None of this is built yet; it is the recorded seam for the eventual Conductor work, and the Methods behind these sequences (XMCD, XMLD, photoemission microscopy, resonant scattering) are carried pending (see [Model](../model.md#deliberately-not-here-yet)).

## Equipment protection

The PSS search-and-secure permit signals, the photon and front-end shutters, and any interlock tier are **absent from dodal** and are not invented here (PSS-1). dodal is a device-control library, not a safety-system description: it carries the motion and optics handles, not the permit leaves behind an interlocked enclosure. CORA names neither a permit signal nor a shutter for i06 until the beamline team supplies them. The Enclosure permit shape and the hazard tier are carried pending at the Diamond Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md)).

## Detectors absent from the control model

Two file-writing seams are not modelled yet because their devices are not in dodal:

- **The i06-1 diffraction scattering detector (DET-1).** Only the detector-arm motors are present in dodal; the scattering detector itself and any incident-flux or drain-current (electron-yield) monitor are absent. The geometry is modelled now; the detector and its file-writing seam are bound later from outside dodal, and no detector Family is invented in the meantime.
- **The PEEM electron-image detector and column (PEEM-1).** dodal binds the PEEM sample manipulator and its energy slit, not the electron-optical column or the magnified-image detector. That column is the `ElectronMicroscope` anatomy, an electron-imaging instrument distinct from the photon `Camera` and from the energy-analyzing catalog `ElectronAnalyzer`; it is deferred, not coined here.

Because both detectors are absent, neither file-writing seam (what each detector writes, and where CORA observes versus owns it) is part of this control model yet. See [Open questions](../questions.md) for the control and safety items still to confirm, and [Model](../model.md#deliberately-not-here-yet) for the deferred detector and Method decisions.
