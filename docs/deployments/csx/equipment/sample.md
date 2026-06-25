# Sample

*The TARDIS diffractometer endstation at 23-ID-1. First cut; PVs read from the profile collection, carried confirm.*

The CSX sample side is the TARDIS endstation: an in-vacuum 6-circle soft X-ray diffractometer that orients the sample and the scattering geometry, with a sample stage, a holography stage, and a cryostat. They are modelled as sample-stage groups in the [descriptor](../inventory.md).

The diffractometer circles bind the catalog `Goniometer` Family and the composed `Assembly(Diffractometer)` (a third hkl diffractometer after 4-ID and 8-ID, now in vacuum); the sample stage reuses `LinearStage` and the cryostat `TemperatureController`. No new family is introduced (see [Model](../model.md#what-this-deployment-graduates)).

## The TARDIS diffractometer (23-ID-1)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `Diffractometer` | `Goniometer` | TARDIS in-vacuum E6C circles theta / delta / gamma + mu; binds the Diffractometer Assembly (`DIFF-1`) |
| `ReciprocalSpace` | `PseudoAxis` | hkl reciprocal-space layer over the E6C geometry; partition rule is `DIFF-2` |
| `SampleStage` | `LinearStage` | sample translation (sx / say / saz) plus the holography sample stage (`SAMPLE-1`) |
| `SampleTemperature` | `TemperatureController` | Lakeshore 336 cryostat controller (`SAMPLE-1`) |

TARDIS is driven through hkl in the E6C geometry, the same reciprocal-space machinery as the 4-ID and 8-ID diffractometers, which is why it reuses the `Goniometer` Family and the `Assembly(Diffractometer)` rather than earning a new shape. The circle roles are `DIFF-1`; the inverse-kinematics partition rule is `DIFF-2`. The fine piezo nanopositioner for sample / lens positioning is present in the config but deferred in this cut.

See [Open questions](../questions.md) for the diffractometer and sample-environment facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
