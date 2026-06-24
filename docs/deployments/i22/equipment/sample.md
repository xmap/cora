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
| `I0` | `FluxMonitor` (loose) | `BL22I-EA-XBPM-02:` | incident-flux ion chamber / XBPM (Tetramm 4-channel current); transmission and dose normalization |
| `It` | `FluxMonitor` (loose) | `BL22I-EA-TTRM-02:` | transmitted-flux ion chamber (Tetramm) |

The flux monitors are carried as a loose `FluxMonitor` family that presents the existing Sensor Role (the Role docstring names ion chambers explicitly). An adversarial new-kind review deferred minting a catalog Family on the strength of I22 alone; whether `FluxMonitor` is earned, or these stay deployment-local Sensor devices, is settled when staff confirm the devices and a rule-of-three fires (FLUX-1). This is the same loose-Sensor pattern 7-BM uses for its `Photodiode` and 2-BM uses for its `BeamPositionMonitor`.

## The sample environment

I22 sample-environment experiments use settable actuators, not just readbacks.

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `SampleTemperature` | `TemperatureController` (loose) | `BL22I-EA-TEMPC-05:` | Linkam temperature controller; a settable setpoint with a readback |
| `SamplePump` | `FlowController` (loose) | `BL22I-EA-PUMP-01:` | Watson-Marlow 323 peristaltic pump; a settable flow actuator |

These present no clean existing Family. An adversarial review found that `GenericProbe` (read-only) would mislabel the actuation, `Positioner` is spatial, and `Controller` acts only through subordinates. The latent fix is a settable-actuator affordance or Role shared with the 7-BM flow controllers, not any current Family-by-settings. Whether CORA commands the setpoints (versus reading them back) and whether that affordance is earned is the load-bearing question, the natural rule-of-three sibling of 7-BM's FLOW-1 (ENV-1).

See [Open questions](../questions.md) for the confirmations still needed and [Inventory](../inventory.md) for the Asset tree.
