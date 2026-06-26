# Sample

*The I22 sample stage. Design-phase; values are reverse-engineered from dodal or inferred.*

The sample stage is the experiment hutch: the sample base and on-axis-view alignment camera, the incident and transmitted flux monitors, and the sample-environment actuators. It is modelled as one sample-environment group in the [descriptor](../inventory.md). There is no rotation stage: I22 is a scattering beamline, not a tomography one, so the tomographic sample tower the imaging pilots model has no analogue here.

## The sample base and alignment

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `SampleBase` | `LinearStage` | `BL22I-MO-STABL-01:` | sample base table; X/Y translation plus a PITCH axis (a TiltStage axis in a per-axis split) |
| `OAV` | `Camera` | `BL22I-DI-OAV-01:` | on-axis-view alignment camera (AVT Mako G-507B); a diagnostic optical camera, distinct from the science detectors. Its working distance and effective pixel size are placeholders in dodal (a sentinel distance and a "double check" pixel size), to be supplied (OAV-1) |

## The flux monitors

The quantitative-flux axis is what the imaging-camera pilots never needed. Two ion chambers read beam current, presenting the existing **Sensor** Role (a scalar Reading, not a 2D frame).

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `I0` | `FluxMonitor` | `BL22I-EA-XBPM-02:` | incident-flux ion chamber / XBPM (Tetramm 4-channel current); transmission and dose normalization |
| `It` | `FluxMonitor` | `BL22I-EA-TTRM-02:` | transmitted-flux ion chamber (Tetramm) |

The flux monitors bind the `FluxMonitor` catalog Family, which presents the existing Sensor Role (the Role docstring names ion chambers explicitly). An adversarial new-kind review deferred minting a Family on the strength of I22 alone; it has since graduated, having reached the rule-of-three across I22, I03, and I15-1 (FLUX-1). It earned its place by what it measures (beam flux, a scalar Reading), the way `EnergyDispersiveSpectrometer` did, and stays distinct from the position-measuring Sensor families still held loose (7-BM's `Photodiode`, 2-BM's `BeamPositionMonitor`).

## The sample environment

I22 sample-environment experiments use settable actuators, not just readbacks.

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `SampleTemperature` | `TemperatureController` | `BL22I-EA-TEMPC-05:` | Linkam temperature controller; a settable setpoint with a readback (the family has since graduated to the catalog, presenting `Regulator`) |
| `SamplePump` | `FlowController` | `BL22I-EA-PUMP-01:` | Watson-Marlow 323 peristaltic pump; a settable flow actuator (the family has since graduated to the catalog, presenting `Regulator`) |

The settable-actuator shape these need is now earned. An adversarial review had found that `GenericProbe` (read-only) would mislabel the actuation, `Positioner` is spatial, and `Controller` acts only through subordinates; the fix was a settable-actuator affordance and Role, which landed in #350 as the `Settable` affordance and the `Regulator` Role. The Linkam binds the graduated `TemperatureController` catalog Family (presents `Regulator`); the pump binds the graduated `FlowController` catalog Family (presents `Regulator`), the `TemperatureController` sibling earned on its own rule-of-three across i22 / 7-BM / LIX / XFP. What stays open is whether CORA commands the setpoints versus reading them back (ENV-1).

See [Open questions](../questions.md) for the confirmations still needed and [Inventory](../inventory.md) for the Asset tree.
