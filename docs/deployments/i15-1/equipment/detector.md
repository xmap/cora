# Detector

*The Eiger on the two-theta arm, plus a second translation and the incident-flux monitor. Design-phase; values are reverse-engineered from dodal or inferred.*

I15-1's detection is the total-scattering shape: a large area detector capturing wide-Q scattering across the two-theta arm, plus an incident-flux monitor for normalization. They are modelled in the detection stage of the [descriptor](../inventory.md).

## The detectors and flux monitor

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `Eiger` | `Camera` | Detector | `BL15I-EA-EIGER-01:` | Dectris Eiger area detector, capturing wide-Q total-scattering frames |
| `Detector2` | `LinearStage` | Positioner | `BL15I-EA-DET-02:` | a second detector translation (y / z) |
| `I0` | `FluxMonitor` (loose) | Sensor | `BL15I-EA-JBPM-03:` | incident-flux monitor (TetrAMM JBPM) for normalization |

## How each maps onto CORA

- **The Eiger reuses `Camera`.** A pixel-array area detector is the Camera Family presenting the Detector Role. The two-theta arm it rides (`TwoTheta`, a `RotaryStage`) is on the [Sample](sample.md) page; the arm geometry and the Eiger threshold / beam-center are calibration dodal does not carry (DET-1).
- **The flux monitor reuses I22's loose `FluxMonitor`.** A TetrAMM ion-chamber readout presenting the Sensor Role, the same shape I22 uses for its i0 / it. This is the **second Diamond deployment** to carry `FluxMonitor`, which builds it toward a rule-of-three graduation into the catalog (FLUX-1).

## Families

The Eiger reuses `Camera`, the second detector translation reuses `LinearStage`, and the flux monitor reuses the loose `FluxMonitor`. No new Family is earned on the detector side. See [Inventory](../inventory.md) for the Asset tree and [Open questions](../questions.md) for the calibration still to confirm.
