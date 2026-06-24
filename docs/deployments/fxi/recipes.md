# Recipes

*Deployment-bound step sequences that expand into Procedures, in ISA-88 shape. Reverse-engineered from the FXI scan plans; carried `confirm` until staff verify.*

A Recipe is a named, deployment-specific sequence with preconditions, steps, and a result. These are read from the FXI bluesky plans.

## energy_setting recipe

Sets the beamline to a target energy by the coupled move that holds magnification constant.

- Source: `move_zp_ccd_xh` (`startup/41-scans.py`).
- Preconditions: the energy-lookup Calibration exists (see [Procedures](procedures.md#energy-lookup-calibration)); target energy within the calibrated 5 to 15 keV range.
- Steps: interpolate the lookup at the target energy, then co-move the DCM (Chi2, Th2), the zone plate (X, Y), the condenser (X, Y1, Y2, P), the aperture (X, Y), and the detector (X, Y) to the interpolated positions.
- Result: the beamline at the target energy with the image still focused and magnified the same. In CORA this is the energy-change Conductor leg.

## dark/flat capture recipe

Captures the reference frames a tomography reconstruction needs.

- Source: `_take_dark_image`, `_take_bkg_image` (`startup/41-scans.py`).
- Steps: close the fast shutter and record dark frames; move the sample out and record flat (white) frames; restore.
- Result: dark and flat frame sets attached to the run. In CORA these are subject-less conducted Runs (the Phase-of-Run pattern), not part of the sample projection set.

## element-edge XANES recipe

Runs energy-resolved imaging across an absorption edge.

- Source: `user_scan`, `_mk_eng_list` (`startup/98-user_scan.py`).
- Steps: build the energy list for the chosen element edge (`_mk_eng_list`), then at each energy run the energy_setting recipe and acquire an image or tomogram.
- Result: a spectro-tomography dataset. Element edges and out-positions are hardcoded per experiment in source, so this Recipe is deployment-bound, not a portable Method.
