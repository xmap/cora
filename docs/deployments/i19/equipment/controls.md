# Controls

*The control stack and the access-control seam. Design-phase, with the dodal-derived handles recorded.*

i19 runs the Diamond EPICS control stack, the same floor as I22, I03, I15-1, I11, I24, I06, I10, and I20-1. As at those beamlines, the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV prefix for each device, so this scaffold carries `pv` on every device.

What sets i19 apart is not its control library but its access-control: two experiment hutches in series share one optics line, and the shared-optics writes do not go straight to EPICS. They pass through a central arbiter. That seam is the centerpiece of this page.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For i19 the EPICS PV prefixes are recorded from dodal (the `src/dodal/beamlines/i19*.py` factories, the `i19_shared` / `i19_1` / `i19_2` device sets, and the `src/dodal/devices/` classes), carried `confirm` because a controls-library snapshot is not a guarantee against the live system (CTRL-1). The PV naming follows the Diamond convention `BL<sector><branch>-<DOMAIN>-<TYPE>-<NN>:` (for example `BL19I-MO-DCM-01:` is beamline 19I, motion domain, double-crystal monochromator 01, and `BL19I-MO-CIRC-02:` is the four-circle goniometer); the undulator uses the `SR19I-MO-SERVC-01:` storage-ring servo root. A handful of representative roots from the walk:

| Handle | Device | Enclosure |
| --- | --- | --- |
| `BL19I-MO-DCM-01:` | `Monochromator` (DCM) | i19-optics |
| `SR19I-MO-SERVC-01:` | `Undulator` | i19-optics |
| `BL19I-OP-STAT-01:EHStatus` | the active-hutch readback (the arbiter's state) | i19-optics |
| `BL19I-MO-CIRC-02:` | `Diffractometer` (Newport kappa four-circle) | i19-2 |
| `BL19I-EA-EIGER-01:` | `Detector` (Eiger) | i19-2 |
| `BL19I-OP-PCOL-01:` | `Aperture` (MAPT pinhole + collimator) | i19-2 |

The full handle list is in the [Inventory](../inventory.md).

What dodal does **not** give, and so is not invented: which access-gated hutch each device sits in (the PV encodes a functional zone, not a hutch or its PSS meaning, ENC-1), the PSS permit leaves behind the interlocked optics shutter (PSS-1), and the calibrated values behind the handles.

## The dual-hutch shared-optics access-control

This is the design-interesting content of i19, and the reason the page exists. EH1 and EH2 sit in series on one optics line, and only the **active hutch** may drive the shared optics. dodal expresses this through a central arbiter, the i19-blueapi optics service, and the distinction CORA carries forward is between reads and writes.

- **Reads are direct.** A hutch, active or not, reads the shared-optics state straight over EPICS. A non-active hutch sees the `Monochromator`, the mirrors, the `Filter` attenuator, and the `Shutter` read-only (MONO-1, ACCESS-1); it just cannot move them.
- **Writes are posted, not direct.** The shared-optics writes (change energy, operate the experiment shutter, move the attenuator, set a mirror piezo) are **not** direct EPICS writes. Each hutch posts the operation to the i19-blueapi arbiter, tagged with its hutch identity. The arbiter compares the requesting hutch against the active-hutch readback (`BL19I-OP-STAT-01:EHStatus`) and either runs the operation or rejects it.

CORA models this without a new device family (ACCESS-1):

- **The shared-optics devices are single Assets** in the `i19-optics` enclosure: the `Monochromator`, the `Undulator`, the two `Mirror`s, the `Filter` attenuator, the `Shutter`, and the `BeamEnergy` pseudo-axis. A non-active hutch reading one of them is the same Asset surfaced through a permit, not a second Asset.
- **The active-hutch permit is an Enclosure-permit + Trust-gate.** EH1 (`i19-1`) and EH2 (`i19-2`) are two `Enclosure`s; which one may drive the shared optics now is a permit axis on the Enclosure, governed by Trust authorization. The `BL19I-OP-STAT-01:EHStatus` readback is the read-model of that permit (ACCESS-1).
- **The i19-blueapi arbiter is an actuate-floor seam partner.** It is the same shape as the "EPICS is the floor" seam the rest of the fleet carries, here a blueapi-arbiter floor: today the arbiter performs the active-hutch arbitration over EPICS. CORA's edge would conduct the run over its `ControlPort`, either **driving through** the arbiter (posting the operation and letting it gate) or **replacing** its plan-orchestration per routine. Which routines drive through and which are replaced is a seam decision not pre-empted in this scaffold (ACCESS-1).

The shared-optics writes that flow through this gate are exactly the ones above:

| Operation | Shared-optics Asset | Family | Gated against |
| --- | --- | --- | --- |
| Change energy | `BeamEnergy` (DCM + undulator + mirror stripe) | PseudoAxis | active-hutch permit (MONO-1, ACCESS-1) |
| Operate the experiment shutter | `OpticsShutter` (`BL19I-PS-SHTR-01`) | Shutter | active-hutch permit (PSS-1, ACCESS-1) |
| Move the attenuator | `Attenuator` (`BL19I-OP-ATTN-04/05`) | Filter | active-hutch permit (ATTN-1, ACCESS-1) |
| Set a mirror piezo | `HorizontalFocusingMirror` / `VerticalFocusingMirror` (`BL19I-OP-HFM-01` / `BL19I-OP-VFM-01`) | Mirror | active-hutch permit (OPT-1, ACCESS-1) |

The mirror coating stripe (Si 5-10 / Rh 10-20 / Pt 20-30 keV) is a hutch-keyed setting on the `Mirror` Asset, not a separate write path; the energy move that selects it is the same gated `BeamEnergy` operation (OPT-1, ACCESS-1). This is the first dual-hutch shared-optics arbitration in the fleet, and it is a governance concern, not a device family.

## Equipment protection

The interlock surface CORA can see today is the dodal `InterlockedHutchShutter`: the experiment shutter (`BL19I-PS-SHTR-01`, modelled as `OpticsShutter`) is PSS-interlocked, so a per-hutch operate of it is gated both by the PSS interlock and by the active-hutch permit above (PSS-1, ACCESS-1).

Beyond that interlocked shutter, the PSS search-and-secure permit signals and the photon / front-end shutters are **not** present in dodal, and so are **not** invented here. The Enclosure permit leaves for EH1, EH2, and the optics, and the safety tier behind them, are named pending confirmation rather than guessed (PSS-1). The Diamond Site governance shape (the operator pool, the safety review, the Clearances) is carried at the Site level, not per beamline, following the 2-BM governance shape (GOV-1).

## The floor: dodal, the blueapi arbiter, and the filestore

A seam observation, recorded for the eventual Conductor work: i19's acquisition floor is the Diamond EPICS / ophyd-async stack, with the device handles above bound from dodal, plus the i19-blueapi optics arbiter that holds the active-hutch arbitration. The arbiter is the actuate-floor seam partner described above: it is what a future CORA edge drives through or replaces per routine, while EPICS stays the floor underneath it (ACCESS-1, CTRL-1).

One surface stays plumbing CORA observes, not data it owns: the Eiger file-writing to the Diamond filestore (`BL19I-EA-EIGER-01`). That is control-system output, not a CORA Asset, recorded because it is what the acquisition seam writes around (DET-1).

See [Open questions](../questions.md) for the control, access-control, and safety items still to confirm, and [Model](../model.md#the-dual-hutch-access-control-seam) for the CORA modelling of the dual-hutch seam.
