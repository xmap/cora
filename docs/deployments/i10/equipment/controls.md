# Controls

*The control stack and the orchestration seam. Design-phase, with the dodal-derived handles recorded.*

i10 runs the Diamond EPICS control stack driven through ophyd-async, the same floor as I22, I03, I15-1, I11, I24, and i06. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS. As at the other Diamond beamlines, the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV root for each device, so this scaffold carries a handle on every Asset. i10 is the fleet's second APPLE-II source after i06, and its soft X-ray twin, so the source-side control story below is the i06 posture reused, not a new one.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For i10 the EPICS PV roots are read from dodal (the `src/dodal/beamlines/i10.py`, `i10_shared.py`, and `i10_1.py` factories and the `src/dodal/devices/` classes) and carried `confirm`, because a controls-library snapshot is not a guarantee against the live system (CTRL-1). The handles follow the Diamond convention, a PV root that encodes a functional zone rather than a hutch. The zones i10 spans:

| PV zone | Carries | Example roots |
| --- | --- | --- |
| `BL10I` | the optics spine: the PGM, the collimating / switching / focusing mirrors, the optics slits | `BL10I-OP-PGM-01:`, `BL10I-OP-SWTCH-01:`, `BL10I-OP-COL-01:` |
| `SR10I` | the APPLE-II servo crates that drive the undulator gaps | `SR10I-MO-SERVC-01:` (downstream IDD), `SR10I-MO-SERVC-21:` (upstream IDU) |
| `ME01D` | the i10-rasor endstation: the diffractometer, the analyzer arm, the cryostat sample stage, the detector channels | `ME01D-MO-DIFF-01:`, `ME01D-MO-POLAN-01:`, `ME01D-MO-CRYO-01:` |
| `BL10J` | the i10-1 / I10J magnet endstation: the electromagnet and superconducting magnet, the magnet stages and optics | `BL10J-EA-MAGC-01:`, `BL10J-EA-SMC-01:` |

The full handle list, Asset by Asset, is in the [Inventory](../inventory.md), and the source walk that binds each one is the generated [Source](../beamline.md) page.

What dodal does **not** give, and so is not invented: which access-gated enclosure each zone maps to (the PV encodes a functional zone, not a hutch or its safety meaning, ENC-1), and the calibrated values behind the handles.

## The APPLE-II controller seam

i10 is CORA's second APPLE-II source after i06, so its run drives the X-ray **polarization** as an experiment axis (linear horizontal LH / vertical LV, circular positive PC / negative NC, linear-arbitrary LA, plus third-harmonic variants) alongside the incident-energy axis. Both are modelled as `PseudoAxis` Assets over the source, reusing the i06 precedent rather than coining anything new. The continuous linear-arbitrary angle is the continuous realization of the LA value **within the same** polarization axis, not a second axis and not a new Family.

The seam to record is that the geometry already lives below CORA. An APPLE-II chooses its polarization by driving its magnetic phase rows, and the live i10 controller holds the energy-to-gap polynomial and the polarization-to-phase conversion for both undulators (the downstream IDD on `SR10I-MO-SERVC-01:` and the upstream IDU on `SR10I-MO-SERVC-21:`). By default that edge controller owns the kinematics:

- CORA **names** the energy and polarization pseudo-axes, **writes** the requested value, and **records** the move.
- The live i10 controller **converts** the value into gap and phase-row positions and drives the servo crates.

So the polarization pseudo-axis is carried **rule-less** (POL-1): the polarization value domain is the axis's value set, but its partition rule lives in the edge controller, not in a CORA Calibration. This is the "edge IOC already computes the geometry" seam, the same posture the energy axis takes over the PGM and the APPLE-II gap (MONO-1). Pinning the conversion as a CORA-owned Calibration is a deferred decision, needed only if CORA must scan polarization without the i10 controller in the loop (POL-1). Both undulators are driven sources; whether the incident-energy axis wires over one gap or two is the question carried as ENERGY-1.

## The orchestration seam

Three sequence families run as bluesky plans over ophyd-async / EPICS today, and that is the seam a CORA edge replaces, conducting over the same floor (i10-1):

- **Resonant scattering and reflectivity scans (RASOR).** The `ME01D-MO-DIFF-01:` diffractometer scan over the two-theta scattering arm and the sample circles (DIFF-1), coordinated by the reciprocal-space pseudo-axis (DIFF-2), with reflectivity the R in RASOR. CORA's edge would conduct that sequence over the goniometer circles and the source axes rather than EPICS owning the loop.
- **Polarization-analysis sequences.** The analyzer arm (the PaStage / POLAN arm, `ME01D-MO-POLAN-01:`) is driven to select the scattered-beam polarization channel alongside the diffractometer move. dodal exposes the arm's motors only; the sequence over those motors is the seam, with no analyzer-crystal specifics invented (POL-2).
- **Applied-field dichroism sequences and field sweeps.** The i10-1 / I10J XMCD / XMLD acquisition over the electromagnet (`BL10J-EA-MAGC-01:`, set-and-read) and the superconducting magnet (`BL10J-EA-SMC-01:`, a flyable field sweep), with the sample at low temperature. The plan steps energy and polarization at an absorption edge while setting or sweeping the field; CORA's edge would conduct that sequence over the source axes and the magnet rather than EPICS owning the loop (MAG-1).

In each case EPICS stays the floor and CORA's edge replaces the bluesky-style orchestration, driving through ophyd-async. None of this is built yet; it is the recorded seam for the eventual conducting work, and the Methods behind these sequences (resonant scattering, reflectivity, XMCD, XMLD) are carried pending (see [Model](../model.md#deliberately-not-here-yet)).

## Equipment protection

The PSS search-and-secure permit signals, the photon and front-end shutters, and any interlock tier are **absent from dodal** and are not invented here (PSS-1). dodal is a device-control library, not a safety-system description: it carries the motion and optics handles, not the permit leaves behind an interlocked enclosure. CORA names neither a permit signal nor a shutter for i10 until the beamline team supplies them.

i10 also carries hazard classes that are governed at the Site, not modelled here: a soft X-ray UHV beamline with an intense polarized beam, high magnetic fields (a superconducting magnet at i10-1), and cryogenics. The Enclosure permit shape and the hazard tier are carried pending at the Diamond Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../diamond/index.md#the-safety-envelope)).

## Detection: point detectors, no area detector

i10 has **no area detector** at either endstation (DET-1). The science detection is point and current-integrating, so the science detector binds the catalog `FluxMonitor` Family rather than a camera or pixel-array detector, and none is invented in the meantime:

- **RASOR point detection (`ME01D`).** The scattered-beam point detector on scaler channel S18, the incident-flux monitor on S17, fluorescence on S19, and the drain-current / total-electron-yield channel on S20, read through Femto / SR570 current amplifiers (DET-1).
- **i10-1 / I10J point detection (`BL10J`).** The TEY / FY / diode / monitor channels, again with no area detector behind them (DET-1).

Because there is no area detector, there is no pixel-array file-writing seam to model; the point channels are the science signal. See [Open questions](../questions.md) for the control, detection, and safety items still to confirm, and [Model](../model.md#deliberately-not-here-yet) for the deferred Method decisions and the held-under-review Families (the loose `PolarizationAnalyzer` on the POLAN arm, POL-2, and the loose `Magnet` shared by both magnet devices, MAG-1).
