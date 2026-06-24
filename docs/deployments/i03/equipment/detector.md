# Detector

*The Eiger and a retractable fluorescence detector. Design-phase; values are reverse-engineered from dodal or inferred.*

I03's detection is the standard MX shape: one large area detector on a translation, plus a retractable fluorescence detector for anomalous and element-identification work. They are modelled in the detection stage of the [descriptor](../inventory.md).

## The detectors

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `Eiger` | `Camera` | Detector | `BL03I-EA-EIGER-01:` | Dectris Eiger area detector, the MX science detector |
| `DetectorMotion` | `LinearStage` | Positioner | `BL03I-MO-DET-01:` | detector translation (z + upstream / downstream x, with a derived yaw); carries an integrated shutter |
| `FluorescenceDetector` | (Sensor, deferred) | Sensor | `BL03I-EA-FLU-01:` | a retractable fluorescence / XRF detector |

## How each maps onto CORA

- **The Eiger reuses `Camera`.** A pixel-array area detector is the Camera Family presenting the Detector Role, the same shape the imaging pilots use; the photon-counting specifics (threshold energy) and the beam-center are calibration dodal does not carry (DET-1).
- **The detector motion is a Positioner.** The translation stage reuses `LinearStage`; its integrated shutter is a Shutter affordance on the same mount. The axis ranges are calibration to confirm.
- **The fluorescence detector presents the Sensor Role.** It reads a scalar / short-vector signal, not a 2D frame, so it is the Sensor Role, not Detector. It is carried loose with its modelling deferred (DET-1), the same loose-Sensor posture 7-BM takes for its energy-dispersive detector and I22 takes for its flux monitors. The retract mechanism is a binary Positioner state, not a separate Family.

## Families

The Eiger reuses `Camera`; the detector motion reuses `LinearStage`. No new Family is earned on the detector side; the fluorescence detector and the sample backlight are carried loose (Sensor and the new `Backlight` family respectively), tracked by DET-1. See [Inventory](../inventory.md) for the Asset tree and [Open questions](../questions.md) for the detector calibration still to confirm.
