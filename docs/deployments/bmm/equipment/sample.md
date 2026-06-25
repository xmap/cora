# Sample

*The endstation XAFS stages: the sample table, the batch sample wheel, and the reference-foil holder. PVs verified against `startup/BMM/user_ns/motors.py`.*

BMM is built for throughput: many samples mounted on a wheel, each indexed into the beam and scanned in turn, with a reference foil measured alongside for energy calibration.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `SampleStage` | LinearStage | `XF:06BM-ES{MC:09}` | sample positioning table (x, y, pitch, roll) |
| `SampleWheel` | RotaryStage | `XF:06BMA-BI{XAFS-Ax:RotB}` | rotating wheel indexing many samples |
| `ReferenceHolder` | LinearStage | `XF:06BMA-BI{XAFS-Ax:RefX}` | reference-foil holder for energy calibration |

## The sample wheel and the sample-changer question

The `SampleWheel` reuses the `RotaryStage` Family: physically it is a rotation axis, and the "wheel of N samples indexed through the beam" is batch automation, a Method/conduct concern, not a new device kind. This is the conservative call at first sighting.

But BMM is not the only deployment with sample-exchange automation: the Diamond MX beamlines (i03) carry a robotic sample changer (family-less, presenting the Positioner Role). Whether a dedicated **sample-changer** abstraction is earned across the BMM wheel and the Diamond robots, or each stays its underlying motion Family, is the open question (WHEEL-1). CORA defers it here rather than minting a `SampleWheel` or `SampleChanger` Family at one sighting.

The reference foil in `ReferenceHolder` is what the `Ir` ion chamber reads (see [Detector](detector.md)): a known standard measured in every scan so the energy axis can be calibrated against its known edge.
