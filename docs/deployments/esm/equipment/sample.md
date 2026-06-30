# Sample

*The ARPES UHV cryostat sample manipulator at 21-ID-D. First cut; PVs read from the profile collection, carried confirm.*

The ESM sample side is a UHV photoemission endstation: a six-axis cryostat manipulator holds the sample at a chosen position, orientation, and low temperature in front of the electron analyzer. They are modelled as a sample-stage group in the [descriptor](../inventory.md).

The cryostat manipulator binds the catalog `Manipulator` Family, which **graduates with this deployment**: ESM is the second UHV sample manipulator after SIX, earning the abstraction once two deployments shared it (see [Model](../model.md#what-this-deployment-graduates)). The temperature controller reuses the catalog `TemperatureController`.

## The UHV sample stack (21-ID-D)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SampleManipulator` | `Manipulator` | LT six-axis UHV cryostat manipulator (x/y/z + Rx/Ry/Rz); the live prefix is the provisional `{PRV`, cryo range and load-lock are `SAMPLE-1` |
| `SampleTemperature` | `TemperatureController` | Lakeshore cryostat controller (Stinger / D3 channels) (`SAMPLE-1`) |

The manipulator orients the sample for the angle-resolved measurement: its rotations set the emission geometry the analyzer reads, and its cryostat holds the sample at low temperature. The live config exposes the manipulator under a provisional `{PRV` prefix (with a commented `{LT:1-Manip:EA5_1` form), so the prefix is `SAMPLE-1`. The sample-prep and analysis-chamber manipulators and the load-lock transfer claw are present in the config but deferred in this cut.

See [Open questions](../questions.md) for the sample-environment facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
