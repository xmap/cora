# tomo-bits versus 2-BM beamline.yaml: Microscope fidelity diff

A PV-by-PV cross-check of CORA's 2-BM `Microscope` model against the working APS 2-BM
tomography instrument. The point is to use the real instrument as evidence for or against
the descriptor, and to surface any divergence as a question for 2-BM staff rather than
editing the descriptor from CORA's own reasoning.

## Sources

- tomo-bits: `BCDA-APS/tomo-bits` at `main`. The authoritative optics artifact is
  `src/tomo_instrument/devices/mct_optics.py` (the `MCTOptics` ophyd class, prefix
  `2bm:MCTOptics:`). The instrument config `src/tomo_instrument/configs/devices.yml` only
  instantiates `MCTOptics` plus simulated devices; the real motors are referenced by name
  inside MCTOptics, not registered in this devices file. So the diff is against the device
  class, not a full inventory.
- CORA: `deployments/2-bm/beamline.yaml`, the Detection stage (`Assembly(Microscope)` over
  the reusable `Optics` sub-assembly), roughly lines 438 to 607.

## Headline

CORA's Microscope model is a strict superset of the tomo-bits MCTOptics class, plus several
staff-verified corrections the device class does not encode. No descriptor change is needed
on the basis of tomo-bits. The diff yields a short list of enrichment questions, of which one
(the `LensSelected` readback) is worth confirming because CORA already depends on it.

## Relation to existing CORA modeling

The current model shipped via the microscope reshape (memory note
`project-microscope-reshape-design`): the Assembly is `Microscope`, the lens picker is an
`objective_selector` PseudoAxis, and per-objective magnification lives on Asset settings with
`magnification` and `effective_thickness` calibration quantities. An earlier deployment plan
(`project-mctoptics-2bm-deployment-design`) assumed a single camera (`camera_select` always 0)
with camera rotation likely unused. tomo-bits corroborates the newer reality that superseded
that assumption: `mct_optics.py` exposes `camera_0` and `camera_1` with `CameraSelect` (0-1)
and a per-camera `RotationPVName`, matching the current descriptor's two cameras (5 MP and
31 MP) and per-camera rotation motors (`2bmb:m7`, `2bmb:m8`). The middle objective also
changed from 5x (old plan) to 2x (current descriptor); tomo-bits does not pin magnifications,
so there is no conflict, only a reminder not to cite the old 5x value.

## PV-by-PV

| MCTOptics PV (mct_optics.py) | Meaning | CORA beamline.yaml | Status |
| --- | --- | --- | --- |
| `LensSelect` (0-2) | select lens | `Objective_Selector.pv 2bm:MCTOptics:LensSelect` | match |
| `Lens` -> `Name0/1/2` | lens slot names | `Objective_Selector.slot_labels_pv [...LensName0..2]` | match |
| `Lens` -> `0/1/2FocusPVName` | per-lens focus motor names | `coupled_lookups.per_lens_focus_pv [2bmb:m2,m3,m4]` | match |
| `Camera0/1` -> `RotationPVName` | per-camera rotation motor names | `coupled_lookups.camera_rotation_pv {camera0:2bmb:m7, camera1:2bmb:m8}` | match |
| `Camera0/1` -> `Pos0/1/2` | turret position per (lens, camera) | `turret_lookup_mm.camera0/camera1` (full 2D table) | CORA ahead (full 2D) |
| `ScintillatorType` | scintillator material | `Scintillator.pv 2bm:MCTOptics:ScintillatorType` | match |
| `DetectorPixelSize` | detector pixel pitch | `Camera.pixel_size 3.45 um` | match |
| `CameraSelect` (0-1) | select camera | `Camera_Selector` (Schunk LPTM 30, `2bmb:m5`) | match on motor; see Q6 |
| `LensSelected` (not in class) | lens readback | `Objective_Selector.readback_pv 2bm:MCTOptics:LensSelected` | divergence; see Q1 |
| `Lens` -> `SampleX/Y/ZPVName`; `Camera{N}Lens{M}` -> `X/Y/ZOffset` | per-(lens,camera) sample offsets | not modeled (CORA models rotation and focus only) | question; see Q2 |
| `ScintillatorThickness` | scintillator thickness | `Scintillator.thickness 100 um` (static) plus a calibration | question; see Q3 |
| `ImagePixelSize` | effective image pixel size | derived (camera pixel size over magnification) | question; see Q4 |
| `CameraObjective`, `CameraTubeLength` | relay optics parameters | not modeled | question; see Q5 |
| `CrossSelect` | crosshair overlay | not modeled | correctly excluded (display) |
| `Sync`, `ServerRunning`, `MCTStatus`, `CameraSelected` (status) | MCTOptics server status | not modeled | correctly excluded (software IOC) |

## Where CORA is ahead

These are real-world facts CORA carries that the tomo-bits device class does not:

- The full two-dimensional `(lens x camera)` turret lookup, both Camera 0 (5 MP) and Camera 1
  (31 MP), operator-verified 2026-06-19 (DET-11). mct_optics.py exposes the position PVs but
  no values.
- Per-unit camera identity: two distinct FLIR Oryx cameras (5 MP `2bmSP1:` serial 19173710,
  31 MP `2bmSP2:` serial 22150530) with firmware and sensor detail (DET-8). The class has a
  generic two-camera structure only.
- The objective selector modeled as a linear ball-screw stage (Nanotec stepper, `2bmb:m1`),
  not a rotating turret, even though the class and its docstring say "turret" (DET-2, DET-11).
- Objective optical constants (numerical aperture, working distance) and per-objective
  magnification calibrations (provisional, energy 25 keV).
- Scintillator material (LuAG), decay time, and an effective-thickness calibration.
- `PropagationDistance` modeled as a distinct sample-to-detector rail (Aerotech, `2bmbAERO:m1`),
  confirmed not a focus motor (DET-10), which the class does not separate from lens focus.

## Correctly excluded

CORA lists MCTOptics as a software IOC that is not modeled as an Asset, so the server control
and status PVs (`Sync`, `ServerRunning`, `MCTStatus`, `CameraSelected` status, `CrossSelect`)
are out of scope by design. The diff confirms the exclusion is complete and intentional.

## Enrichment questions for 2-BM staff

These are candidate questions, not yet filed in `docs/deployments/2-bm/questions.md`. If
promoted they would take real per-section ids. Priority follows the questions.md scale
(`Blocks-go-live` means a real value is needed before CORA controls or observes the hardware;
`Nice-to-have` is for the record).

1. `Blocks-go-live`. CORA's `Objective_Selector.readback_pv` is `2bm:MCTOptics:LensSelected`.
   The tomo-bits MCTOptics class binds `CameraSelected` but does not bind a `LensSelected`
   readback. Does `2bm:MCTOptics:LensSelected` exist on the live IOC? CORA depends on it for
   the objective readback.
2. `Nice-to-have`. MCTOptics references sample X, Y, Z motor names and carries per-(lens,
   camera) X, Y, Z offsets. Does selecting an objective also command sample re-centering
   offsets that CORA should model, in addition to the rotation and focus it already tracks?
3. `Nice-to-have`. `ScintillatorThickness` is a live PV in MCTOptics. CORA records a static
   100 um plus a provisional effective-thickness calibration. Is the scintillator thickness
   operator-changed in operation (multiple scintillators), which would make a live read more
   appropriate than a static value?
4. `Nice-to-have`. MCTOptics publishes a computed `ImagePixelSize`. CORA derives the effective
   image pixel size from the camera pixel size and the objective magnification. Should CORA
   capture the MCTOptics-computed value as a calibration instead of deriving it?
5. `Nice-to-have`. `CameraObjective` and `CameraTubeLength` are relay-optics parameters that
   can change effective magnification independently of the objective. Should CORA capture them,
   or are they fixed and already folded into the per-objective magnification?
6. `Nice-to-have`. CORA models the camera selector as a motor (`Camera_Selector`, `2bmb:m5`).
   MCTOptics exposes a high-level `CameraSelect` (0-1) pseudo, analogous to `LensSelect`.
   Should CORA carry a `CameraSelect` virtual axis alongside the selector motor, mirroring
   `Objective_Selector`?

## Recommendation

No `beamline.yaml` change on the basis of tomo-bits; CORA is ahead. Treat
`tomo-bits/mct_optics.py` as external corroboration that the MCTOptics PV structure CORA
models is real. Route the six questions to 2-BM staff, deferring physical facts to the
operator and `2bm-docs`, never to CORA's internal consistency. The one to prioritize is Q1,
the `LensSelected` readback, since the descriptor already asserts that PV. The other channel
worth a look is `tomo-bits/plans/dm_plans.py`, the APS Data Management workflow handoff, which
scopes the post-Run compute and transfer leg that CORA's Reckoner and Porter edge runtimes
will eventually call or replace.
