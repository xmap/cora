# Techniques

*What FXI can do, as portable [Catalog](../../catalog/methods.md) Methods. Each would be bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). The function view survives equipment swaps.*

FXI's techniques are reverse-engineered from the bluesky scan plans in `startup/41-scans.py`, `42-scans_legacy.py`, `43-scans_pzt.py`, `44-scans_other.py`, and `46-zebra_flyer.py`. Each maps to a Catalog Method that already exists for the 2-BM pilot, which is the point: a second tomography deployment proves the Methods are portable across facilities.

## Imaging

| What | Catalog Method | FXI plan | Notes |
| --- | --- | --- | --- |
| Continuous-rotation fly tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | `fly_scan`, `tomo_zfly` | Zebra position-triggered; the core technique |
| Step tomography | [`tomography`](../../catalog/methods.md) | `tomo_scan` | stop-and-shoot projections |
| Mosaic tomography | [`mosaic_tomography`](../../catalog/methods.md) | `tomo_mosaic_scan` | tiled fields for large samples |
| Radiography | [`tomography`](../../catalog/methods.md) | `radiography_scan` | single-angle projection series; carried under the tomography family pending a dedicated Method |
| Flat / dark acquisition | [`flat_field`](../../catalog/methods.md), [`dark_field`](../../catalog/methods.md) | `_take_bkg_image`, `_take_dark_image` | reference frames, captured per scan |

## Spectroscopy

| What | Catalog Method | FXI plan | Notes |
| --- | --- | --- | --- |
| XANES imaging / spectro-tomography | [`tomography`](../../catalog/methods.md) + [`beamline_energy_change`](../../catalog/methods.md) | `xanes_scan`, `xanes_3D`, `multi_edge_xanes_zebra` | energy-resolved imaging; each energy step is an energy change |
| Energy change | [`beamline_energy_change`](../../catalog/methods.md) | `move_zp_ccd_xh` | the coupled energy move (see [Recipes](recipes.md)) |

## Supporting operations

| What | Catalog Method | FXI plan | Notes |
| --- | --- | --- | --- |
| Rotation-center finding | [`center_alignment`](../../catalog/methods.md) | `find_rot`, `rotcen_test` | from `startup/94-tomo_recon.py` |
| Calibration-position recording | [`focus_alignment`](../../catalog/methods.md) | `record_calib_pos_new_xh`, `trans_calib_xh` | builds the energy lookup table |

Reconstruction (TomoPy `gridrec` / `astra` / iterative, ring removal, rotation-center search) is the compute leg, mapped to the Reckoner / `ComputePort` rather than a beamline Method; see [Controls](equipment/controls.md#the-seam-cora-and-the-epics-floor).
