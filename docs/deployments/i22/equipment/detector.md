# Detector

*Two area detectors, read simultaneously. Design-phase; values are reverse-engineered from dodal or inferred.*

The detector-side shape of a scattering beamline is two area detectors run at once: a SAXS detector at long camera length and a WAXS detector at short camera length. They are modelled in the detection stage of the [descriptor](../inventory.md). Both present the **Detector** Role (2D frames), the same Role the imaging pilots use; what is new is that there are two of them, the same model at different positions, and the beamstops that protect them.

## The detectors and beamstops

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `SaxsDetector` | `Camera` | Detector | `BL22I-EA-PILAT-01:` | Dectris Pilatus3 2M, photon-counting hybrid pixel, 0.172 mm pixel, Si 0.45 mm sensor (dodal); long camera length |
| `WaxsDetector` | `Camera` | Detector | `BL22I-EA-PILAT-03:` | a second Pilatus3 2M, identical hardware, short camera length |
| `BeamStop1` | `BeamStop` | (positioned) | `BL22I-MO-SAXSP-01:BS1:` | SAXS beamstop, positioned X/Y |
| `BeamStop2` | `BeamStop` | (positioned) | `BL22I-MO-SAXSP-01:BS2:` | SAXS beamstop, positioned X/Y |
| `BeamStop3` | `BeamStop` | (positioned) | `BL22I-MO-SAXSP-01:BS3:` | SAXS beamstop, positioned X/Y + roll |

## How each maps onto CORA

- **SAXS and WAXS are one Family, two Assets.** Both are the same Dectris Pilatus3 2M. The difference is the camera length (long for small-angle, short for wide-angle) and the technique role, both of which are settings and placement, not a Family split. This is exactly the per-instance modelling CORA prefers over per-technique subtypes: two `Camera` Assets distinguished by distance and the Capability they serve.
- **The beamstops are modelled as the thing, not its motion.** dodal carries the beamstops as XY (and XY+roll) positioning stages. CORA models them as `BeamStop` Assets whose positioning is an affordance, not as bare stages: the thing on the beam is a beam-absorbing stop that happens to be positionable. The beam-effect (what fraction it absorbs) stays deferred, the same passive beam-path posture the other deployments take.

## What dodal cannot give the detectors

Three detector facts are calibration dodal does not carry, and they are required for real SAXS/WAXS data reduction:

- **Camera lengths as a range.** dodal carries a single distance snapshot for each detector. Whether the detector distance is a fixed mount or a settable axis (a movable detector or flight tube) decides whether a detector-translation `LinearStage` Asset is warranted (DET-1).
- **Threshold energy.** The photon-counting Pilatus threshold is `None` in dodal; it is a beam-energy-dependent calibrated value (DET-2).
- **Beam-center.** The per-detector beam-center is `None` in dodal and is required to reduce a pattern to q-space (DET-2).

## Families

Both detectors reuse `Camera`; the beamstops reuse `BeamStop`. No new Family is earned on the detector side. See [Inventory](../inventory.md) for the Asset tree and [Open questions](../questions.md) for the detector calibration still to confirm.
