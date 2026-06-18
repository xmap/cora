# Techniques

*What 2-BM can do: the measurements and operations this beamline offers, each realizing a cross-facility Catalog
technique.*

This is the function view, the most swap-stable way to navigate the beamline: a technique survives an equipment
change, so it bridges the portable [Catalog](../../catalog/index.md) vocabulary (the
[Methods](../../catalog/methods.md) and the [Capabilities](../../catalog/capabilities.md) they realize) to this
beamline's [as-built](as-built.md) hardware and its [Operations](operations.md) runbook. Each technique names the
Method it runs: the Method is portable, the binding to 2-BM hardware is local.

## Imaging

The core science output. All four realize the `cora.capability.tomography` Capability and need the
[Microscope](equipment/microscope.md) detector and the [Sample tower](equipment/sample_tower.md) positioner.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Tomography | `tomography` | step-scan projections over a rotation |
| Continuous-rotation tomography | `continuous_rotation_tomography` | fly-scan, rotation never stops |
| Streaming tomography | `streaming_tomography` | projections streamed for live reconstruction |
| Mosaic tomography | `mosaic_tomography` | sample-tower XY tiling for a field wider than the detector |

Laminography is not a separate Method: the sample tower carries a permanently-installed laminography tilt, so a
laminographic scan is a tomography Plan run at a tilt setpoint over the same tower (see
[Sample tower](equipment/sample_tower.md)).

## Energy

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Energy change (Mono / Pink) | `beamline_energy_change` | drives the monochromator and mirror to a configured energy; realizes `cora.capability.energy_change` |

Run it through [Operations](operations.md): the `set_energy` Procedure and the
[`set_energy`](recipes.md#set_energy) recipe.

## Supporting operations

The capabilities that make a measurement possible rather than producing the science data, run as
[Procedures](procedures.md) and [Recipes](recipes.md) under [Operations](operations.md):

| Capability | Catalog methods |
| --- | --- |
| `cora.capability.alignment` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment` |
| `cora.capability.characterization` | `sensitivity_characterization` (and the energy-offset `energy_characterization`) |
| `cora.capability.acquisition` | `first_light`, `dark_baseline`, `flat_baseline` |
| `cora.capability.maintenance` | `motor_homing`, `hexapod_reboot` |
