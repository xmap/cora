# Techniques

*What CORA would run at FXI: the Capabilities and portable [Catalog](../../catalog/methods.md) Methods CORA brings, bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). The function view survives equipment swaps.*

FXI is a full-field transmission X-ray microscope that does fly and step tomography, mosaic tomography, radiography, and XANES / spectro-tomography. These are the same techniques the 2-BM pilot exercised, so CORA expresses each as a Catalog Method it already carries: a second tomography deployment proves the Methods are portable across facilities. (The "demonstrated by" column names the floor plan that shows FXI runs the technique today; CORA replaces that orchestration with its Conductor, see [Controls](equipment/controls.md#the-seam-cora-and-the-floor).)

## Imaging

| CORA does | Catalog Method | Demonstrated by (floor) |
| --- | --- | --- |
| Continuous-rotation fly tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | position-triggered fly scan |
| Step tomography | [`tomography`](../../catalog/methods.md) | stop-and-shoot projections |
| Mosaic tomography | [`mosaic_tomography`](../../catalog/methods.md) | tiled fields for large samples |
| Radiography | [`tomography`](../../catalog/methods.md) | single-angle projection series (carried under the tomography family pending a dedicated Method) |
| Flat / dark acquisition | [`flat_field`](../../catalog/methods.md), [`dark_field`](../../catalog/methods.md) | reference-frame capture per scan |

## Spectroscopy

| CORA does | Catalog Method | Demonstrated by (floor) |
| --- | --- | --- |
| XANES imaging / spectro-tomography | [`tomography`](../../catalog/methods.md) + [`beamline_energy_change`](../../catalog/methods.md) | energy-resolved imaging across an edge |
| Energy change | [`beamline_energy_change`](../../catalog/methods.md) | the coupled energy move (see [Recipes](recipes.md)) |

## Supporting operations

| CORA does | Catalog Method | Demonstrated by (floor) |
| --- | --- | --- |
| Rotation-center finding | [`center_alignment`](../../catalog/methods.md) | center search during reconstruction |
| Calibration-position recording | [`focus_alignment`](../../catalog/methods.md) | building the energy lookup table |

Reconstruction (the tomographic recon, ring removal, rotation-center search) is CORA's compute leg, conducted over the ComputePort rather than as a beamline Method; see [Controls](equipment/controls.md#the-seam-cora-and-the-floor).
