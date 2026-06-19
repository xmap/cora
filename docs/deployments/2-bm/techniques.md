# Techniques

*What 2-BM can do. Each technique runs a portable [Catalog](../../catalog/methods.md) Method, bound to this
beamline's [hardware](beamline.md) and [Operations](operations.md). This function view survives equipment swaps.*

## Imaging

All realize `cora.capability.tomography` and need the [Microscope](equipment/microscope.md) detector and the
[Sample tower](equipment/sample_tower.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Tomography | `tomography` | step-scan projections over a rotation |
| Continuous-rotation tomography | `continuous_rotation_tomography` | fly-scan, rotation never stops |
| Streaming tomography | `streaming_tomography` | projections streamed for live reconstruction |
| Mosaic tomography | `mosaic_tomography` | XY tiling for a field wider than the detector |

Laminography is a tomography Plan run at a tilt setpoint on the same tower, not a separate Method.

## Energy

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Energy change (Mono / Pink) | `beamline_energy_change` | drives the monochromator and mirror to a configured energy |

Run it via [Operations](operations.md): the `energy_setting` Procedure and [recipe](recipes.md#energy_setting).

## Supporting operations

Run as [Procedures](procedures.md) and [Recipes](recipes.md) under [Operations](operations.md):

| Capability | Catalog methods |
| --- | --- |
| `alignment` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment` |
| `characterization` | `sensitivity_characterization`, `energy_characterization` |
| `acquisition` | `first_light`, `dark_baseline`, `flat_baseline` |
| `maintenance` | `motor_homing`, `hexapod_reboot` |
