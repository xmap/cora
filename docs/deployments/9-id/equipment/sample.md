# Sample

*The grazing-incidence CSSI sample stack at 9-ID-D. First cut; PVs read from the beamline config, carried confirm.*

The 9-ID sample side is a coherent surface scattering stack: a translation stage places the sample surface in the focused beam, and an incidence rotation sets the shallow grazing angle that makes the measurement surface-sensitive. Around it sit two alignment hexapods and an on-axis viewing microscope. They are modelled as sample-stage groups in the [descriptor](../inventory.md).

Every device here binds a catalog Family: the grazing-incidence geometry is modelled with `LinearStage` and `RotaryStage`, the alignment stages with the catalog `Hexapod` Family, and the viewing microscope with `Camera`. Whether the stack composes into a sample Assembly is deferred to a second grazing-incidence beamline (`CSSI-1`).

## The grazing-incidence stack (9-ID-D)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `CSSISampleStage` | `LinearStage` | sample translation (x/y/z) plus the Aerotech fly-scan Z and a GIXS sample x (`CSSI-1`) |
| `CSSIIncidence` | `RotaryStage` | the grazing-incidence rotation that sets the shallow surface angle (`CSSI-1`) |
| `Hexapod_1` / `Hexapod_2` | `Hexapod` | Aerotech six-axis alignment hexapods (`CSSI-2`) |
| `ViewingMicroscope` | `Camera` | on-axis sample-viewing microscope (an optical alignment camera, not the TXM Microscope Assembly) (`CSSI-3`) |

The incidence rotation is the defining degree of freedom: in grazing-incidence scattering the angle between the surface and the beam is the controlled quantity, so `CSSIIncidence` is what a surface-scattering Plan scans. Which motor sets that angle, and the translation-versus-rotation split across the CSSI stack, is `CSSI-1`.

A sample-positioning Kohzu stage (`kohzu_linear` / `kohzu_rotate`) is present in the config and folded into the descriptor note pending its role; the simulated sample motors are excluded.

See [Open questions](../questions.md) for the sample-geometry facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
