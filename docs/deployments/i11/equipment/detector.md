# Detector

*The Mythen3 position-sensitive strip detector. Design-phase; values are reverse-engineered from dodal or inferred.*

I11's detection is a single position-sensitive strip detector that reads a 1D diffraction pattern across the two-theta arm. It is modelled in the detection stage of the [descriptor](../inventory.md).

## The detector

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `Mythen3` | `Camera` | Detector | `BL11I-EA-DET-07:` | Dectris/PSI Mythen3 position-sensitive strip detector; skip-flagged in dodal (issue I11-916) |

## How it maps onto CORA

- **The Mythen3 reuses `Camera` (Detector Role), with a noted nuance.** The Detector Role is defined for image-emitting detectors; a Mythen3 is a 1D *strip* (a line of channels) producing a powder-diffraction pattern, not a 2D frame. It reuses `Camera`/Detector as the closest existing shape, but whether a strip / position-sensitive detector warrants a distinct family or Role is the open question (MYTHEN-1). Carrying it as `Camera` avoids minting a kind on a single deployment; the strip-vs-2D distinction is recorded, not resolved.
- **It is skip-flagged in dodal.** The dodal `mythen3` factory carries `skip=True` (the detector state does not match ophyd-async, issue I11-916), so the device shape is dry-correct but its runtime is unverified; the threshold and deadtime values are calibration to supply (MYTHEN-1).

## Families

The Mythen3 reuses `Camera`. No new Family is earned on the detector side in this scaffold; the strip-detector Role question is tracked by MYTHEN-1. See [Inventory](../inventory.md) and [Open questions](../questions.md).
