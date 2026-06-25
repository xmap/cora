# Sample

*The experiment-hutch sample side: the diffractometer, the sample-array stage, the pinhole, and the sample environment. PVs verified against `startup/10-motors.py` and `startup/11-temperature-controller.py`.*

XPD places a powder or capillary sample in the high-energy beam and records its diffraction or total-scattering pattern. Much of XPD's science is in the sample environment: the same powder measured across a temperature ramp is how phase transitions and thermal structure are studied.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleStage` | LinearStage | `XF:28IDC-ES:1{Dif:1}` | holds the sample and the detector arm |
| `SampleArrayStage` | LinearStage | `XF:28IDC-ES:1{SampArray}` | presents many samples for high throughput |
| `Pinhole` | Aperture | `XF:28IDC-ES:1{PinHole:XRD}` | cleans the beam onto the sample |
| `SampleTemperature` | TemperatureController | `XF:28IDC-ES:1{CS:800}` | cryostream / furnace thermal environment |

## The diffractometer and sample stages

The `SampleStage` is the diffractometer (`Dif:1`: theta, X, Y, and inboard/outboard two-theta) that holds the sample and the detector arm. CORA binds it to `LinearStage` as a design-phase placeholder; the diffractometer carries goniometric (rotation) axes, so whether its orientation is modelled as a `Goniometer` plus a Diffractometer Assembly, the shape Diamond [I11](../../i11/equipment/sample.md) and APS 8-ID use, is folded into STAGE-1. The `SampleArrayStage` presents many samples in a row for unattended high-throughput acquisition, fed by the sample-changing robot (ROBOT-1). The `Pinhole` cleans the beam onto the sample, reusing the `Aperture` family.

## Sample environment

XPD carries a rich sample-environment cluster: the `cs700` and `cs800` cryostream controllers (understood to be Oxford Cryostreams, an inference pending TEMP-1), Eurotherm and hot-air blowers, a Lakeshore cryostat, and a Linkam furnace. CORA models them as one `SampleTemperature` Asset (the cryostream is canonical) and reuses the `TemperatureController` family, the same Family Diamond [I11](../../i11/index.md) graduated for exactly this, variable-temperature powder diffraction (TEMP-1). This is the reuse point: the continuous-setpoint thermal actuator that earns its keep at a powder beamline is the same one that serves spectroscopy (BMM) and coherence (CHX). Which units are live is TEMP-1.
