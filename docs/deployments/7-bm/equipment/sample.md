# Sample

*The 7-BM sample stage. Design-phase; values are taken from the 7-BM docs or inferred.*

The sample stage is the 7-BM-B experiment hutch: the tomography rotation and sample positioning, the energy-dispersive gauge slits, and the flow and combustion sample environment that distinguishes 7-BM from the 2-BM micro-CT pilot. It is modelled as one sample-stage group in the [descriptor](../inventory.md).

Unlike 2-BM, which models its sample positioning as a `SampleTower` Assembly plus Fixture, the 7-BM sample stage is carried as a plain device group in this scaffold. It could earn the Assembly shape once the manipulator firms and a scenario registers it.

## The positioning stack

The tomography path reuses the 2-BM shape: a rotation stage driven by the same tomoScan engine, with a sample-positioning stage for centring.

| Device | Family | Notes (from the 7-BM docs) |
| --- | --- | --- |
| `TomographyRotation` | `RotaryStage` | sample rotation for tomography; tomoScan-driven (single, vertical, horizontal, mosaic), the same engine 2-BM uses |
| `SamplePositioning` | `LinearStage` | sample centring and translation |
| `EDDSlit` | `Slit` | energy-dispersive-diffraction gauge slits: two tungsten-carbide blocks 511 mm apart, curved for a 3 degree full scattering angle at 150 mm working distance; defines the gauge volume the germanium detector sees |

## The flow and combustion sample environment

This is the 7-BM-specific axis. Flow and combustion experiments draw on a compressed-air plant (a Kaeser compressor with accumulator tanks and an electronic regulator), a high-volume vacuum system (two rotary-claw pumps), and metered process gases. The continuously-available services are modelled as facility [Supplies](../inventory.md) (compressed air, vacuum, process gas), not as beam-path devices. What is modelled here is the settable flow control:

| Device | Family | Notes (from the 7-BM docs) |
| --- | --- | --- |
| `FlowController` | `FlowController` (loose) | Sierra Smart-Trak mass-flow controllers (three units, Kr and N2 ranges) metering process gas. A settable actuator with a commanded setpoint and a flow readback, unlike any 2-BM device |

Two questions shape this part of the model:

- **Does CORA command the setpoints?** The flow controllers and the electronic air regulator are settable, not just readable. The settable-actuator *shape* is now settled: the `TemperatureController` graduation (the i11 rule-of-three) added the `Settable` affordance and the `Regulator` Role, which a `FlowController` would present. What stays open for 7-BM (FLOW-1) is whether CORA commands the setpoints (versus reading them back) and whether `FlowController` itself graduates: it is loose at only 7-BM and I22, short of its own rule-of-three.
- **Is there a combustion rig?** The compressed-air, gas, and vacuum infrastructure serves flow and combustion experiments, but whether an installed combustion, spray, or fuel-injection device exists (versus combustion being an intended use of the infrastructure) is unconfirmed (ENV-1). Until it is, no combustion-rig Asset is modelled; the specimen carries the hazard on its Subject.

The flammable-gas, fuel-vapor, and oxygen-deficiency hazards this environment adds are governance, handled at the [APS Site](../../aps/index.md#the-safety-envelope) by clearances and operator Cautions; whether they need a workflow beyond the standard ESAF is HAZ-1 on [Governance](../governance.md).

See [Open questions](../questions.md) for the confirmations still needed and [Inventory](../inventory.md) for the Asset tree.
