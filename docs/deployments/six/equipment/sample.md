# Sample

*The UHV cryostat sample manipulator and the endstation optics at 2-ID-D. First cut; PVs read from the profile collection, carried confirm.*

The SIX sample side is a soft X-ray RIXS endstation under ultra-high vacuum: a cryostat manipulator holds the sample at a chosen position, angle, and temperature in front of the spectrometer arm, with endstation mirrors steering the focused beam onto it. They are modelled as sample-stage groups in the [descriptor](../inventory.md).

The cryostat manipulator binds a loose `Manipulator` Family (no catalog motion Family fits a UHV multi-axis cryo manipulator; see [Model](../model.md#new-loose-families)); the endstation mirrors reuse the catalog `Mirror` Family, and the temperature controller the catalog `TemperatureController`.

## The UHV sample stack (2-ID-D)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `SampleManipulator` | `Manipulator` (loose) | UHV cryostat manipulator (x/y/z/theta); cryo range and load-lock are `SAMPLE-1` |
| `SampleChamber` | `LinearStage` | sample-chamber pivot translation; the spectrometer arm swings about it (`RIXS-1`) |
| `Mirror_5` / `Mirror_6` | `Mirror` | endstation mirrors; M5 carries the optics-wheel theta (`OPT-1`) |
| `MirrorMask_5` | `Aperture` | single-axis mask at M5 (`OPT-2`) |
| `SampleTemperature` | `TemperatureController` | Lakeshore 336 sample temperature controller (`SAMPLE-1`) |

The sample theta on the manipulator and the sample-chamber pivot together set the scattering geometry the spectrometer arm reads; how the arm pivots about the sample chamber is `RIXS-1`. The UHV and cryogenic environment is the new sample-environment regime soft X-ray brings to the fleet; its base pressure, cryo range, and any sample-transfer load-lock are `SAMPLE-1`.

See [Open questions](../questions.md) for the sample-environment facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
